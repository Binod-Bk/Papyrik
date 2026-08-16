"""QThread wrappers. No long PDF operation runs on the UI thread.

- `OperationWorker` runs any pure `core` function off-thread and reports the
  result (usually an output path) or a human-readable error.
- `ThumbnailWorker` renders a document's pages to PNG bytes one at a time and
  streams them back, so opening a 300-page file never freezes the window.

The UI connects to these signals; it never calls a `core` operation directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal

from papyrik.core import batch
from papyrik.core.document import PdfDocument


class OperationWorker(QThread):
    """Runs `fn(*args, **kwargs)` off the UI thread."""

    finished_ok = pyqtSignal(object)  # result (usually an output path)
    failed = pyqtSignal(str)          # human-readable error message

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:  # QThread entry point
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # corrupt PDFs are normal, not exceptional
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(result)


class BatchWorker(QThread):
    """Runs a folder batch off the UI thread, reporting per-file progress."""

    progress = pyqtSignal(int, int)     # done, total
    finished_ok = pyqtSignal(object)    # list[BatchResult]
    failed = pyqtSignal(str)

    def __init__(self, folder, operation, output_dir, *,
                 ext: str = "pdf", suffix: str = "") -> None:
        super().__init__()
        self._folder = folder
        self._operation = operation
        self._output_dir = output_dir
        self._ext = ext
        self._suffix = suffix

    def run(self) -> None:
        try:
            results = batch.run_batch(
                self._folder, self._operation, self._output_dir,
                ext=self._ext, suffix=self._suffix,
                progress=lambda done, total: self.progress.emit(done, total),
            )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(results)


class ThumbnailWorker(QThread):
    """Renders each page of `path` to PNG bytes and emits them in order.

    Opens its own PdfDocument handle so the render loop never shares a PyMuPDF
    document with the UI thread. Honors interruption so a superseded load stops
    promptly.
    """

    thumbnail_ready = pyqtSignal(int, bytes)  # page index, PNG bytes
    done = pyqtSignal()

    def __init__(self, path: str | Path, password: str | None = None,
                 dpi: int = 30) -> None:
        super().__init__()
        self._path = path
        self._password = password
        self._dpi = dpi

    def run(self) -> None:
        try:
            doc = PdfDocument(self._path, self._password)
        except Exception:
            self.done.emit()
            return
        try:
            for i in range(doc.page_count):
                if self.isInterruptionRequested():
                    break
                try:
                    data = doc.render_png(i, dpi=self._dpi)
                except Exception:
                    continue
                self.thumbnail_ready.emit(i, data)
        finally:
            doc.close()
        self.done.emit()

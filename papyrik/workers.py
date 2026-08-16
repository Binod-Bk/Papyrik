"""QThread wrappers. No long PDF operation runs on the UI thread.

`OperationWorker` runs any pure `core` function on a background thread and
emits progress / finished / failed signals. The UI connects to these; it never
calls a `core` operation directly.
"""

from __future__ import annotations

from typing import Any, Callable

from PyQt6.QtCore import QObject, QThread, pyqtSignal


class OperationWorker(QThread):
    """Runs `fn(*args, **kwargs)` off the UI thread.

    A callable passed as the `progress` keyword (if the operation supports it)
    should accept an int 0-100. Result and errors come back via signals.
    """

    progress = pyqtSignal(int)
    finished_ok = pyqtSignal(object)  # result (usually an output path)
    failed = pyqtSignal(str)          # human-readable error message

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:  # noqa: D401 - QThread entry point
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # corrupt PDFs are normal, not exceptional
            self.failed.emit(str(exc))
            return
        self.finished_ok.emit(result)

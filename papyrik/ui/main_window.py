"""Main window shell and orchestrator.

    [ sidebar tool list ] | [ central page preview ] | [ right-hand tool panel ]

MainWindow owns the open-document state and the undo stack, and turns preview
gestures into page operations. Every operation runs off the UI thread via
`workers`; the window never calls a `core` operation directly on the GUI thread.

Version model: opening a file seeds an undo stack of file *versions* in a
private temp dir. Each page op writes a new version and pushes it; undo pops
back. The user's original file is never modified - an encrypted file is first
decrypted into a working copy so pure operations never see a password.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from papyrik import APP_NAME, __version__
from papyrik.core.document import (
    PdfCorruptError,
    PdfDocument,
    PdfEncryptedError,
    is_encrypted,
)
from papyrik.core.operations import convert, pages
from papyrik.ui.page_viewer import PageViewer
from papyrik.ui.thumbnail_view import ThumbnailView
from papyrik.ui.tool_panel import ToolPanel
from papyrik.workers import OperationWorker, ThumbnailWorker

TOOLS: list[tuple[str, list[str]]] = [
    ("Pages", ["Merge", "Split", "Rotate", "Delete", "Extract", "Reorder"]),
    ("Convert", ["PDF to Word", "PDF to Images", "Images to PDF", "PDF to Text"]),
    ("Enhance", ["Compress", "Watermark", "Page Numbers"]),
    ("Security", ["Encrypt", "Decrypt", "Metadata"]),
    ("Annotate", ["Highlight", "Sticky Note", "Draw"]),
    ("Forms", ["Fill Form"]),
    ("Batch", ["Batch Folder"]),
]


class Sidebar(QListWidget):
    """Flat tool list with non-selectable group headers."""

    def __init__(self) -> None:
        super().__init__()
        self.setMaximumWidth(200)
        for group, tools in TOOLS:
            header = QListWidgetItem(group.upper())
            header.setFlags(Qt.ItemFlag.NoItemFlags)
            self.addItem(header)
            for tool in tools:
                item = QListWidgetItem("   " + tool)
                item.setData(Qt.ItemDataRole.UserRole, tool)
                self.addItem(item)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        # -- document state --
        self._workdir = Path(tempfile.mkdtemp(prefix="papyrik_"))
        self._versions: list[Path] = []
        self._counter = 0
        self._busy = False
        self._saved = True  # False once there are edits not yet exported

        self._op_worker: OperationWorker | None = None
        self._thumb_worker: ThumbnailWorker | None = None

        # -- panes --
        self.sidebar = Sidebar()
        self.preview = ThumbnailView()
        self.tool_panel = ToolPanel()

        self.sidebar.currentItemChanged.connect(self._on_tool_changed)
        self.preview.reorder_requested.connect(self._on_reorder)
        self.preview.rotate_requested.connect(self._on_rotate)
        self.preview.delete_requested.connect(self._on_delete)
        self.preview.extract_requested.connect(self._on_extract)
        self.preview.page_activated.connect(self._on_view_page)
        self.tool_panel.run_requested.connect(self._on_run_tool)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self._wrap(self.preview))
        splitter.addWidget(self.tool_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 700, 300])
        self.setCentralWidget(splitter)

        self.setStatusBar(QStatusBar())
        self._build_actions()
        self._refresh_actions()
        self._status(f"{APP_NAME} {__version__} — open a PDF to begin")

    # -- layout helpers ---------------------------------------------------

    @staticmethod
    def _wrap(widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget)
        return container

    def _build_actions(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        self.act_open = file_menu.addAction("&Open…")
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.open_file)

        self.act_merge = file_menu.addAction("&Merge PDFs…")
        self.act_merge.triggered.connect(self.merge_files)

        self.act_save = file_menu.addAction("Save &As…")
        self.act_save.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save.triggered.connect(self.save_as)

        file_menu.addSeparator()
        act_quit = file_menu.addAction("&Quit")
        act_quit.setShortcut("Ctrl+Q")
        act_quit.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu("&Edit")
        self.act_undo = edit_menu.addAction("&Undo")
        self.act_undo.setShortcut(QKeySequence.StandardKey.Undo)
        self.act_undo.triggered.connect(self.undo)

        page_menu = self.menuBar().addMenu("&Pages")
        self.act_split = page_menu.addAction("&Split every N pages…")
        self.act_split.triggered.connect(self.split_every_n)

    # -- state ------------------------------------------------------------

    @property
    def _current(self) -> Path | None:
        return self._versions[-1] if self._versions else None

    def _next_path(self) -> Path:
        self._counter += 1
        return self._workdir / f"v{self._counter}.pdf"

    def _refresh_actions(self) -> None:
        has_doc = self._current is not None
        self.act_save.setEnabled(has_doc and not self._busy)
        self.act_split.setEnabled(has_doc and not self._busy)
        self.act_undo.setEnabled(len(self._versions) > 1 and not self._busy)
        self.act_open.setEnabled(not self._busy)
        self.act_merge.setEnabled(not self._busy)

    def _status(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._busy = busy
        self.preview.setEnabled(not busy)
        if message:
            self._status(message)
        self._refresh_actions()

    # -- open -------------------------------------------------------------

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF files (*.pdf)"
        )
        if path:
            self._open_path(Path(path))

    def _open_path(self, path: Path) -> None:
        try:
            encrypted = is_encrypted(path)
        except PdfCorruptError as exc:
            self._error("Cannot open file", str(exc))
            return

        working = path
        if encrypted:
            working = self._decrypt_to_workdir(path)
            if working is None:
                return  # user cancelled or gave up

        self._versions = [working]
        self._saved = True  # freshly opened; no unsaved edits yet
        # NB: never reset self._counter here - _next_path() must stay monotonic
        # within the per-session workdir, or a later op can overwrite the base
        # version (breaks undo, notably after decrypting an encrypted file).
        self._load_current(f"Opened {path.name}")

    def _decrypt_to_workdir(self, path: Path) -> Path | None:
        """Prompt for the password and write a plaintext working copy."""
        while True:
            password, ok = QInputDialog.getText(
                self, "Password required",
                f"'{path.name}' is protected. Enter password:",
                QLineEdit.EchoMode.Password,
            )
            if not ok:
                return None
            try:
                with PdfDocument(path, password) as doc:
                    return doc.save_as(self._next_path())
            except PdfEncryptedError:
                self._error("Wrong password", "That password did not work.")
            except Exception as exc:  # noqa: BLE001
                self._error("Cannot open file", str(exc))
                return None

    # -- thumbnails -------------------------------------------------------

    def _load_current(self, message: str = "") -> None:
        current = self._current
        if current is None:
            self.preview.clear()
            self._refresh_actions()
            return
        try:
            with PdfDocument(current) as doc:
                count = doc.page_count
        except Exception as exc:  # noqa: BLE001
            self._error("Cannot read document", str(exc))
            return

        self.preview.set_page_count(count)
        self._start_thumbnails(current)
        if message:
            self._status(f"{message} — {count} page{'s' if count != 1 else ''}")
        self._refresh_actions()

    def _start_thumbnails(self, path: Path) -> None:
        self._stop_thumbnails()
        worker = ThumbnailWorker(path)
        worker.thumbnail_ready.connect(self.preview.set_thumbnail)
        self._thumb_worker = worker
        worker.start()

    def _stop_thumbnails(self) -> None:
        if self._thumb_worker is not None:
            self._thumb_worker.requestInterruption()
            self._thumb_worker.wait()
            self._thumb_worker = None

    # -- operation plumbing ----------------------------------------------

    def _run_version_op(self, fn, *args) -> None:
        """Run a page op that produces a new document version."""
        if self._busy or self._current is None:
            return
        out = self._next_path()
        self._set_busy(True, "Working…")

        def on_ok(result: object) -> None:
            self._versions.append(Path(str(result)))
            self._saved = False
            self._set_busy(False)
            self._load_current("Done")

        self._launch(fn, *args, out, on_ok=on_ok)

    def _launch(self, fn, *args, on_ok) -> None:
        worker = OperationWorker(fn, *args)

        def handle_fail(message: str) -> None:
            self._set_busy(False)
            self._error("Operation failed", message)

        def cleanup() -> None:
            # Runs after run() has fully exited, so deleting the QThread is safe
            # (avoids "QThread: Destroyed while thread is still running").
            if self._op_worker is worker:
                self._op_worker = None
            worker.deleteLater()

        worker.finished_ok.connect(on_ok)
        worker.failed.connect(handle_fail)
        worker.finished.connect(cleanup)
        self._op_worker = worker
        worker.start()

    # -- preview gesture handlers ----------------------------------------

    def _on_reorder(self, order: list[int]) -> None:
        self._run_version_op(pages.reorder, self._current, order)

    def _on_rotate(self, indices: list[int], degrees: int) -> None:
        self._run_version_op(pages.rotate, self._current, indices, degrees)

    def _on_delete(self, indices: list[int]) -> None:
        self._run_version_op(pages.delete_pages, self._current, indices)

    def _on_extract(self, indices: list[int]) -> None:
        if self._busy or self._current is None:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Extract pages to", "extract.pdf", "PDF files (*.pdf)"
        )
        if not out:
            return
        self._set_busy(True, "Extracting…")

        def on_ok(result: object) -> None:
            self._set_busy(False)
            self._status(f"Extracted {len(indices)} page(s) to {Path(str(result)).name}")

        self._launch(pages.extract_pages, self._current, indices, out, on_ok=on_ok)

    def _on_view_page(self, index: int) -> None:
        if self._current is None or self._busy:
            return
        try:
            with PdfDocument(self._current) as doc:
                count = doc.page_count
            viewer = PageViewer(self._current, index, count, self)
        except Exception as exc:  # noqa: BLE001
            self._error("Cannot open page", str(exc))
            return
        viewer.exec()

    # -- undo / save ------------------------------------------------------

    def undo(self) -> None:
        if len(self._versions) > 1 and not self._busy:
            self._versions.pop()
            if len(self._versions) == 1:
                self._saved = True  # back to the originally opened document
            self._load_current("Undone")

    def save_as(self) -> None:
        if self._current is None:
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Save PDF as", "", "PDF files (*.pdf)"
        )
        if not out:
            return
        try:
            shutil.copyfile(self._current, out)
        except OSError as exc:
            self._error("Save failed", str(exc))
            return
        self._saved = True
        self._status(f"Saved {Path(out).name}")

    # -- merge / split ----------------------------------------------------

    def merge_files(self) -> None:
        if self._busy:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDFs to merge (in order)", "", "PDF files (*.pdf)"
        )
        if len(files) < 2:
            if files:
                self._error("Merge", "Select at least two files to merge.")
            return
        out = self._next_path()
        self._set_busy(True, "Merging…")

        def on_ok(result: object) -> None:
            self._versions = [Path(str(result))]
            self._saved = False  # merged output exists only in the workdir
            self._set_busy(False)
            self._load_current("Merged")

        self._launch(pages.merge, [Path(f) for f in files], out, on_ok=on_ok)

    def split_every_n(self) -> None:
        if self._busy or self._current is None:
            return
        n, ok = QInputDialog.getInt(
            self, "Split", "Pages per file:", 1, 1, 10000
        )
        if not ok:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Save split files to")
        if not out_dir:
            return
        self._set_busy(True, "Splitting…")

        def on_ok(result: object) -> None:
            self._set_busy(False)
            count = len(result) if isinstance(result, list) else 0
            self._status(f"Split into {count} files in {Path(out_dir).name}")

        self._launch(pages.split_every_n, self._current, n, out_dir, on_ok=on_ok)

    # -- convert ----------------------------------------------------------

    def _on_run_tool(self, tool: str) -> None:
        handlers = {
            "PDF to Word": self._convert_to_word,
            "PDF to Images": self._convert_to_images,
            "Images to PDF": self._images_to_pdf,
            "PDF to Text": self._convert_to_text,
        }
        handler = handlers.get(tool)
        if handler is not None:
            handler()

    def _need_document(self) -> bool:
        if self._busy:
            return False
        if self._current is None:
            self._error("No document", "Open a PDF first.")
            return False
        return True

    def _export(self, fn, *args, busy: str, done: str) -> None:
        """Run an export op (does not touch the version stack)."""
        self._set_busy(True, busy)

        def on_ok(result: object) -> None:
            self._set_busy(False)
            self._status(done)

        self._launch(fn, *args, on_ok=on_ok)

    def _convert_to_word(self) -> None:
        if not self._need_document():
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Convert to Word", "", "Word documents (*.docx)"
        )
        if not out:
            return
        self._export(convert.pdf_to_docx, self._current, out,
                     busy="Converting to Word…",
                     done=f"Saved {Path(out).name} (best effort on layout)")

    def _convert_to_text(self) -> None:
        if not self._need_document():
            return
        out, _ = QFileDialog.getSaveFileName(
            self, "Extract Text", "", "Text files (*.txt)"
        )
        if not out:
            return
        self._set_busy(True, "Extracting text…")

        def on_ok(result: object) -> None:
            self._set_busy(False)
            path = Path(str(result))
            text = path.read_text(encoding="utf-8", errors="replace")
            if text.strip():
                self._status(f"Saved {path.name}")
            else:
                QMessageBox.information(
                    self, "No text found",
                    "This PDF has no extractable text layer - it looks scanned "
                    "or image-only, so the file was saved empty.\n\n"
                    "Papyrik doesn't do OCR (out of scope). To capture the "
                    "pages as images instead, use PDF to Images.",
                )
                self._status("No text layer found - saved empty file")

        self._launch(convert.pdf_to_text, self._current, out, on_ok=on_ok)

    def _convert_to_images(self) -> None:
        if not self._need_document():
            return
        fmt, ok = QInputDialog.getItem(
            self, "Export Images", "Format:", ["png", "jpg"], 0, False
        )
        if not ok:
            return
        out_dir = QFileDialog.getExistingDirectory(self, "Save images to")
        if not out_dir:
            return
        self._export(convert.pdf_to_images, self._current, out_dir, fmt,
                     busy="Rendering images…",
                     done=f"Exported images to {Path(out_dir).name}")

    def _images_to_pdf(self) -> None:
        if self._busy:
            return
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select images (in order)", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.tiff *.gif)"
        )
        if not files:
            return
        out = self._next_path()
        self._set_busy(True, "Building PDF…")

        def on_ok(result: object) -> None:
            self._versions = [Path(str(result))]
            self._saved = False
            self._set_busy(False)
            self._load_current("Built PDF from images")

        self._launch(convert.images_to_pdf, [Path(f) for f in files], out,
                     on_ok=on_ok)

    # -- misc -------------------------------------------------------------

    def _on_tool_changed(self, current, _previous) -> None:
        if current is None:
            return
        tool = current.data(Qt.ItemDataRole.UserRole)
        if tool:
            self.tool_panel.show_tool(tool)

    def _error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
        self._status(message)

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._current is not None and not self._saved:
            choice = QMessageBox.warning(
                self, "Unsaved changes",
                "You have edits that haven't been saved to a PDF.\n"
                "Save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel,
                QMessageBox.StandardButton.Save,
            )
            if choice == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if choice == QMessageBox.StandardButton.Save:
                self.save_as()
                if not self._saved:  # user backed out of the save dialog
                    event.ignore()
                    return

        self._stop_thumbnails()
        if self._op_worker is not None:
            self._op_worker.wait()
        shutil.rmtree(self._workdir, ignore_errors=True)
        super().closeEvent(event)

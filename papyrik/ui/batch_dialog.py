"""Batch dialog - apply one operation to every PDF in a folder.

Self-contained: it gathers an input folder, an operation (with any params), and
an output folder, then runs a BatchWorker off the UI thread with a progress bar
and a per-file result log. Independent of the open document.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from papyrik.core.operations import convert, enhance, security
from papyrik.workers import BatchWorker

_OPERATIONS = ["Compress", "Watermark (text)", "Page numbers",
               "Encrypt", "Decrypt", "PDF to Word", "PDF to Text"]


class BatchDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Batch — process a folder")
        self.setMinimumWidth(560)
        self._in_dir = ""
        self._out_dir = ""
        self._worker: BatchWorker | None = None

        self._in_label = QLabel("(none)")
        self._out_label = QLabel("(none)")
        in_btn = QPushButton("Choose…")
        out_btn = QPushButton("Choose…")
        in_btn.clicked.connect(self._pick_input)
        out_btn.clicked.connect(self._pick_output)

        self._op = QComboBox()
        self._op.addItems(_OPERATIONS)

        form = QFormLayout()
        form.addRow("Input folder:", self._row(self._in_label, in_btn))
        form.addRow("Operation:", self._op)
        form.addRow("Output folder:", self._row(self._out_label, out_btn))

        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setPlaceholderText("Results will appear here.")

        self._run = QPushButton("Run")
        self._run.clicked.connect(self._start)
        close = QPushButton("Close")
        close.clicked.connect(self.reject)
        actions = QHBoxLayout()
        actions.addStretch(1)
        actions.addWidget(self._run)
        actions.addWidget(close)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self._progress)
        layout.addWidget(self._log, 1)
        layout.addLayout(actions)
        self.resize(600, 480)

    @staticmethod
    def _row(label: QLabel, button: QPushButton) -> QWidget:
        host = QWidget()
        row = QHBoxLayout(host)
        row.setContentsMargins(0, 0, 0, 0)
        label.setWordWrap(True)  # readable default text color; wrap long paths
        row.addWidget(label, 1)
        row.addWidget(button)
        return host

    def _pick_input(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Folder of PDFs to process")
        if path:
            self._in_dir = path
            self._in_label.setText(path)

    def _pick_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Where to save results")
        if path:
            self._out_dir = path
            self._out_label.setText(path)

    # -- operation binding ------------------------------------------------

    def _build_operation(self):
        """Return (op, ext, suffix) for the chosen operation, or None."""
        name = self._op.currentText()
        if name == "Compress":
            preset, ok = QInputDialog.getItem(
                self, "Compress", "Quality:", ["high", "balanced", "low"], 1, False)
            if not ok:
                return None
            return (lambda s, d: enhance.compress(s, d, preset), "pdf", "_compressed")
        if name == "Watermark (text)":
            text, ok = QInputDialog.getText(
                self, "Watermark", "Watermark text:", QLineEdit.EchoMode.Normal,
                "CONFIDENTIAL")
            if not ok or not text.strip():
                return None
            return (lambda s, d: enhance.watermark(s, d, text=text),
                    "pdf", "_watermarked")
        if name == "Page numbers":
            return (lambda s, d: enhance.page_numbers(s, d), "pdf", "_numbered")
        if name == "Encrypt":
            pw, ok = QInputDialog.getText(
                self, "Encrypt", "Password:", QLineEdit.EchoMode.Password)
            if not ok or not pw:
                return None
            return (lambda s, d: security.encrypt(s, pw, d), "pdf", "_encrypted")
        if name == "Decrypt":
            pw, ok = QInputDialog.getText(
                self, "Decrypt", "Password:", QLineEdit.EchoMode.Password)
            if not ok:
                return None
            return (lambda s, d: security.decrypt(s, pw, d), "pdf", "_decrypted")
        if name == "PDF to Word":
            return (lambda s, d: convert.pdf_to_docx(s, d), "docx", "")
        if name == "PDF to Text":
            return (lambda s, d: convert.pdf_to_text(s, d), "txt", "")
        return None

    # -- run --------------------------------------------------------------

    def _start(self) -> None:
        if self._worker is not None:
            return
        if not self._in_dir or not self._out_dir:
            self._log.setText("Choose both an input folder and an output folder.")
            return
        built = self._build_operation()
        if built is None:
            return
        operation, ext, suffix = built

        self._run.setEnabled(False)
        self._log.clear()
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)  # busy until first tick

        worker = BatchWorker(self._in_dir, operation, self._out_dir,
                             ext=ext, suffix=suffix)
        worker.progress.connect(self._on_progress)
        worker.finished_ok.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(self._cleanup)
        self._worker = worker
        worker.start()

    def _on_progress(self, done: int, total: int) -> None:
        self._progress.setRange(0, total)
        self._progress.setValue(done)

    def _on_done(self, results: list) -> None:
        ok = [r for r in results if r[2] is None]
        failed = [r for r in results if r[2] is not None]
        lines = [f"Processed {len(results)} file(s): "
                 f"{len(ok)} succeeded, {len(failed)} failed."]
        for path, _out, err in failed:
            lines.append(f"  ✗ {path.name}: {err}")
        if not results:
            lines = ["No PDF files found in the input folder."]
        self._log.setText("\n".join(lines))

    def _on_failed(self, message: str) -> None:
        self._log.setText(f"Batch failed: {message}")

    def _cleanup(self) -> None:
        self._progress.setVisible(False)
        self._run.setEnabled(True)
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        if self._worker is not None:
            self._worker.wait()
        super().closeEvent(event)

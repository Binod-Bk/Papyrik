"""Right-hand tool panel - shows the selected tool's description and, for
implemented tools, a Run button that emits `run_requested(tool_name)`.

MainWindow owns the actual operation dispatch (dialogs, workers); this panel
stays presentation-only.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

TOOL_HINTS: dict[str, str] = {
    "Merge": "Combine several PDFs into one file. (File ▸ Merge PDFs…)",
    "Split": "Split by page range or every N pages. (Pages ▸ Split…)",
    "Rotate": "Right-click pages in the grid to rotate them.",
    "Delete": "Select pages and right-click ▸ Delete.",
    "Extract": "Select pages and right-click ▸ Extract to new PDF.",
    "Reorder": "Drag pages in the grid, or use Ctrl+←/→.",
    "PDF to Word": "Export to .docx. Best effort on complex layouts.",
    "PDF to Images": "Render each page to PNG or JPEG.",
    "Images to PDF": "Combine image files into a single PDF.",
    "PDF to Text": "Extract the text layer to a .txt file.",
    "Compress": "Reduce file size - three quality presets.",
    "Watermark": "Text or image, with opacity/rotation/position.",
    "Page Numbers": "Stamp page numbers.",
    "Encrypt": "Password-protect the PDF.",
    "Decrypt": "Remove a known password.",
    "Metadata": "View and edit document metadata.",
    "Highlight": "Highlight text.",
    "Sticky Note": "Add a text note annotation.",
    "Draw": "Freehand drawing.",
    "Fill Form": "Fill existing AcroForm fields.",
    "Batch Folder": "Apply an operation to every PDF in a folder.",
}

# Tools driven by this panel's Run button -> label shown on the button.
RUN_LABELS: dict[str, str] = {
    "PDF to Word": "Convert to Word…",
    "PDF to Images": "Export Images…",
    "Images to PDF": "Choose Images…",
    "PDF to Text": "Extract Text…",
    "Encrypt": "Set Password…",
    "Decrypt": "Remove Password…",
    "Compress": "Compress…",
    "Watermark": "Add Watermark…",
    "Page Numbers": "Add Page Numbers…",
    "Metadata": "View / Edit…",
    "Highlight": "Highlight a page…",
    "Sticky Note": "Add notes to a page…",
    "Draw": "Draw on a page…",
    "Fill Form": "Fill Form…",
    "Batch Folder": "Open Batch…",
}


class ToolPanel(QWidget):
    run_requested = pyqtSignal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._title = QLabel("Select a tool")
        self._title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._hint = QLabel("Pick a tool from the sidebar to begin.")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: palette(mid);")

        self._run = QPushButton()
        self._run.setVisible(False)
        self._run.clicked.connect(self._on_run)

        layout.addWidget(self._title)
        layout.addWidget(self._hint)
        layout.addSpacing(12)
        layout.addWidget(self._run)

        self._current: str | None = None

    def show_tool(self, tool: str) -> None:
        self._current = tool
        self._title.setText(tool)
        self._hint.setText(TOOL_HINTS.get(tool, "Not yet implemented."))
        label = RUN_LABELS.get(tool)
        self._run.setVisible(label is not None)
        if label:
            self._run.setText(label)

    def _on_run(self) -> None:
        if self._current:
            self.run_requested.emit(self._current)

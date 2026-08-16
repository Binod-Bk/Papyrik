"""Right-hand tool panel — swaps its controls per selected sidebar tool.

Scaffold: each tool shows its name and a one-line description. Real controls
(range pickers, opacity sliders, etc.) are added per operation in later prompts.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget

TOOL_HINTS: dict[str, str] = {
    "Merge": "Combine several PDFs into one file.",
    "Split": "Split by page range or every N pages.",
    "Rotate": "Rotate selected pages 90/180/270°.",
    "Delete": "Remove selected pages.",
    "Extract": "Save selected pages as a new PDF.",
    "Reorder": "Drag pages in the grid to reorder.",
    "PDF to Word": "Export to .docx (best effort on complex layouts).",
    "PDF to Images": "Render each page to PNG/JPEG.",
    "Images to PDF": "Combine images into a single PDF.",
    "PDF to Text": "Extract the text layer.",
    "Compress": "Reduce file size — three quality presets.",
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


class ToolPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setMinimumWidth(260)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._title = QLabel("Select a tool")
        self._title.setStyleSheet("font-size: 16px; font-weight: 600;")
        self._hint = QLabel("Pick a tool from the sidebar to begin.")
        self._hint.setWordWrap(True)
        self._hint.setStyleSheet("color: palette(mid);")

        self._layout.addWidget(self._title)
        self._layout.addWidget(self._hint)

    def show_tool(self, tool: str) -> None:
        self._title.setText(tool)
        self._hint.setText(TOOL_HINTS.get(tool, "Not yet implemented."))

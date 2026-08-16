"""Main window shell — three panes:

    [ sidebar tool list ] | [ central page preview ] | [ right-hand tool panel ]

This module owns layout and wiring only. Page rendering lives in
`thumbnail_view`, per-tool controls in `tool_panel`, and all PDF work happens
off the UI thread via `workers`.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QSplitter,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from papyrik import APP_NAME, __version__
from papyrik.ui.thumbnail_view import ThumbnailView
from papyrik.ui.tool_panel import ToolPanel

# Sidebar tool groups, mirroring the day plan in CLAUDE.md.
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

        self.sidebar = Sidebar()
        self.preview = ThumbnailView()
        self.tool_panel = ToolPanel()

        self.sidebar.currentItemChanged.connect(self._on_tool_changed)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.sidebar)
        splitter.addWidget(self._wrap_preview())
        splitter.addWidget(self.tool_panel)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 700, 300])

        self.setCentralWidget(splitter)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage(f"{APP_NAME} {__version__} — open a PDF to begin")

        self._build_menu()

    def _wrap_preview(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.preview)
        return container

    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = file_menu.addAction("&Open…")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_file)
        file_menu.addSeparator()
        quit_action = file_menu.addAction("&Quit")
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", "", "PDF files (*.pdf)"
        )
        if not path:
            return
        # Wiring to PdfDocument comes in a later prompt.
        self.statusBar().showMessage(f"Selected: {path}")

    def _on_tool_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            return
        tool = current.data(Qt.ItemDataRole.UserRole)
        if tool:
            self.tool_panel.show_tool(tool)

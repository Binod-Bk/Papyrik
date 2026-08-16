"""Central page preview — a grid of page thumbnails.

Scaffold: shows a placeholder until a document is loaded. Multi-select,
drag-to-reorder, and context-menu page ops arrive in the page-ops prompt.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListWidget,
    QListView,
    QStackedWidget,
)


class ThumbnailView(QStackedWidget):
    """Stacks an empty-state placeholder over the page grid."""

    def __init__(self) -> None:
        super().__init__()

        self._placeholder = QLabel("No document open.\nFile ▸ Open… to load a PDF.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: palette(mid); font-size: 14px;")

        self._grid = QListWidget()
        self._grid.setViewMode(QListView.ViewMode.IconMode)
        self._grid.setResizeMode(QListView.ResizeMode.Adjust)
        self._grid.setMovement(QListView.Movement.Static)
        self._grid.setSpacing(12)
        self._grid.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        self.addWidget(self._placeholder)
        self.addWidget(self._grid)
        self.setCurrentWidget(self._placeholder)

    def clear(self) -> None:
        self._grid.clear()
        self.setCurrentWidget(self._placeholder)

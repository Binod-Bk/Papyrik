"""Central page preview - a grid of page thumbnails.

Owns display and gestures only; it emits *intent* signals (reorder, rotate,
delete, extract) that MainWindow turns into real page operations off-thread.
Each grid item carries its source page index (0-based) in UserRole, so the
window can map a gesture back to page numbers regardless of visual order.
"""

from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QImage, QPixmap
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QLabel,
    QListView,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QStackedWidget,
)

_PAGE_ROLE = Qt.ItemDataRole.UserRole
_ICON = QSize(150, 200)


class _Grid(QListWidget):
    """Icon grid with internal-move reordering and a page context menu."""

    reorder_requested = pyqtSignal(list)          # new order of page indices
    rotate_requested = pyqtSignal(list, int)      # indices, degrees
    delete_requested = pyqtSignal(list)           # indices
    extract_requested = pyqtSignal(list)          # indices

    def __init__(self) -> None:
        super().__init__()
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Static)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setSpacing(12)
        self.setIconSize(_ICON)
        self.setGridSize(QSize(_ICON.width() + 24, _ICON.height() + 36))
        self.setUniformItemSizes(True)
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

    # -- reordering -------------------------------------------------------

    def visual_order(self) -> list[int]:
        return [self.item(row).data(_PAGE_ROLE) for row in range(self.count())]

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        before = self.visual_order()
        super().dropEvent(event)
        after = self.visual_order()
        if after != before:
            self.reorder_requested.emit(after)

    # -- selection --------------------------------------------------------

    def selected_indices(self) -> list[int]:
        return sorted(i.data(_PAGE_ROLE) for i in self.selectedItems())

    # -- context menu -----------------------------------------------------

    def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt override
        indices = self.selected_indices()
        if not indices:
            item = self.itemAt(event.pos())
            if item is None:
                return
            item.setSelected(True)
            indices = [item.data(_PAGE_ROLE)]

        menu = QMenu(self)
        n = len(indices)
        noun = "page" if n == 1 else f"{n} pages"
        menu.addAction(f"Rotate {noun} right 90°",
                       lambda: self.rotate_requested.emit(indices, 90))
        menu.addAction(f"Rotate {noun} left 90°",
                       lambda: self.rotate_requested.emit(indices, -90))
        menu.addAction(f"Rotate {noun} 180°",
                       lambda: self.rotate_requested.emit(indices, 180))
        menu.addSeparator()
        menu.addAction(f"Extract {noun} to new PDF…",
                       lambda: self.extract_requested.emit(indices))
        menu.addAction(f"Delete {noun}",
                       lambda: self.delete_requested.emit(indices))
        menu.exec(event.globalPos())


class ThumbnailView(QStackedWidget):
    """Stacks an empty-state placeholder over the page grid."""

    reorder_requested = pyqtSignal(list)
    rotate_requested = pyqtSignal(list, int)
    delete_requested = pyqtSignal(list)
    extract_requested = pyqtSignal(list)

    def __init__(self) -> None:
        super().__init__()

        self._placeholder = QLabel("No document open.\nFile ▸ Open… to load a PDF.")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("color: palette(mid); font-size: 14px;")

        self._grid = _Grid()
        self._grid.reorder_requested.connect(self.reorder_requested)
        self._grid.rotate_requested.connect(self.rotate_requested)
        self._grid.delete_requested.connect(self.delete_requested)
        self._grid.extract_requested.connect(self.extract_requested)

        self.addWidget(self._placeholder)
        self.addWidget(self._grid)
        self.setCurrentWidget(self._placeholder)

    # -- population -------------------------------------------------------

    def set_page_count(self, count: int) -> None:
        """Reset the grid to `count` numbered placeholder items."""
        self._grid.clear()
        for i in range(count):
            item = QListWidgetItem(f"Page {i + 1}")
            item.setData(_PAGE_ROLE, i)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setSizeHint(QSize(_ICON.width() + 20, _ICON.height() + 30))
            self._grid.addItem(item)
        self.setCurrentWidget(self._grid if count else self._placeholder)

    def set_thumbnail(self, index: int, data: bytes) -> None:
        """Fill in the icon for page `index` from PNG bytes."""
        if not 0 <= index < self._grid.count():
            return
        image = QImage()
        image.loadFromData(data, "PNG")
        self._grid.item(index).setIcon(QIcon(QPixmap.fromImage(image)))

    def selected_indices(self) -> list[int]:
        return self._grid.selected_indices()

    def clear(self) -> None:
        self._grid.clear()
        self.setCurrentWidget(self._placeholder)

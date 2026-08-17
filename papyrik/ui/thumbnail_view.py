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
    QVBoxLayout,
    QWidget,
)

from papyrik.resources import resource_path

_PAGE_ROLE = Qt.ItemDataRole.UserRole
_ASPECT = 1.414                       # ~A4 (height / width)
_ZOOM_WIDTHS = [100, 130, 170, 210, 270, 340]  # icon widths per zoom step
_DEFAULT_ZOOM = 3                     # -> 210 px


def compute_reorder(count: int, src_rows: list[int], drop_row: int) -> list[int]:
    """New row order after moving `src_rows` so they land at `drop_row`.

    `drop_row` is an insertion point in original-row coordinates (0..count).
    Pure and side-effect free so it can be unit-tested without a drag gesture.
    """
    src = list(dict.fromkeys(src_rows))  # de-dup, keep order
    src_set = set(src)
    remaining = [r for r in range(count) if r not in src_set]
    insert_pos = sum(1 for r in remaining if r < drop_row)
    return remaining[:insert_pos] + src + remaining[insert_pos:]


class _Grid(QListWidget):
    """Icon grid with internal-move reordering and a page context menu."""

    reorder_requested = pyqtSignal(list)          # new order of page indices
    rotate_requested = pyqtSignal(list, int)      # indices, degrees
    delete_requested = pyqtSignal(list)           # indices
    extract_requested = pyqtSignal(list)          # indices
    page_activated = pyqtSignal(int)              # double-clicked page index

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("pageGrid")
        self.setViewMode(QListView.ViewMode.IconMode)
        self.setResizeMode(QListView.ResizeMode.Adjust)
        self.setMovement(QListView.Movement.Snap)
        self.setFlow(QListView.Flow.LeftToRight)
        self.setWrapping(True)
        self.setSpacing(14)
        self.setUniformItemSizes(True)
        self._zoom = _DEFAULT_ZOOM
        self._apply_zoom()
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.DefaultContextMenu)

        self._drag_rows: list[int] = []

        self.itemDoubleClicked.connect(
            lambda item: self.page_activated.emit(item.data(_PAGE_ROLE))
        )

    # -- zoom -------------------------------------------------------------

    def _apply_zoom(self) -> None:
        width = _ZOOM_WIDTHS[self._zoom]
        height = round(width * _ASPECT)
        self.setIconSize(QSize(width, height))
        self.setGridSize(QSize(width + 28, height + 40))
        for row in range(self.count()):
            self.item(row).setSizeHint(QSize(width + 20, height + 30))

    def item_size_hint(self) -> QSize:
        width = _ZOOM_WIDTHS[self._zoom]
        return QSize(width + 20, round(width * _ASPECT) + 30)

    def set_zoom(self, index: int) -> bool:
        index = max(0, min(len(_ZOOM_WIDTHS) - 1, index))
        if index == self._zoom:
            return False
        self._zoom = index
        self._apply_zoom()
        return True

    def zoom_in(self) -> bool:
        return self.set_zoom(self._zoom + 1)

    def zoom_out(self) -> bool:
        return self.set_zoom(self._zoom - 1)

    def reset_zoom(self) -> bool:
        return self.set_zoom(_DEFAULT_ZOOM)

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            (self.zoom_in if event.angleDelta().y() > 0 else self.zoom_out)()
            event.accept()
        else:
            super().wheelEvent(event)

    # -- reordering -------------------------------------------------------

    def visual_order(self) -> list[int]:
        return [self.item(row).data(_PAGE_ROLE) for row in range(self.count())]

    def startDrag(self, actions) -> None:  # noqa: N802 - Qt override
        # Record the dragged rows now; the selection is reliable here, whereas
        # at drop time it may have changed.
        self._drag_rows = sorted(self.row(i) for i in self.selectedItems())
        super().startDrag(actions)

    # Accept internal moves everywhere so dropEvent is actually delivered
    # (over items and empty space alike), rather than the drop being refused.
    def dragEnterEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
            event.accept()
        else:
            event.ignore()

    def _drop_row(self, event) -> int:
        """Insertion point (0..count) from the cursor position at drop time."""
        pos = event.position().toPoint()
        index = self.indexAt(pos)
        if not index.isValid():
            return self.count()  # dropped past the last item
        row = index.row()
        rect = self.visualRect(index)
        # Past the horizontal midpoint of the target -> insert after it.
        if pos.x() > rect.center().x():
            row += 1
        return row

    def _apply_move(self, rows: list[int], drop_row: int) -> None:
        """Move item `rows` so they land at insertion point `drop_row`.

        Rearranges the QListWidgetItems directly (take/insert) - deterministic
        and independent of Qt's IconMode internal move.
        """
        rows = sorted(rows)
        insert_at = drop_row - sum(1 for r in rows if r < drop_row)
        taken = [self.takeItem(r) for r in reversed(rows)][::-1]
        for offset, item in enumerate(taken):
            self.insertItem(insert_at + offset, item)
        self.clearSelection()
        for row in range(insert_at, insert_at + len(taken)):
            self.item(row).setSelected(True)

    def dropEvent(self, event) -> None:  # noqa: N802 - Qt override
        rows = self._drag_rows or sorted(self.row(i) for i in self.selectedItems())
        self._drag_rows = []
        if not rows:
            event.ignore()
            return
        self._apply_move(rows, self._drop_row(event))
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        self.reorder_requested.emit(self.visual_order())

    def move_selected(self, direction: str) -> None:
        """Nudge the selected pages one position 'left' or 'right'.

        Moves the selection as a block; a no-op at the respective edge.
        """
        rows = sorted(self.row(i) for i in self.selectedItems())
        if not rows:
            return
        if direction == "left":
            if rows[0] == 0:
                return
            drop_row = rows[0] - 1
        else:  # right
            if rows[-1] >= self.count() - 1:
                return
            drop_row = rows[-1] + 2
        self._apply_move(rows, drop_row)
        self.reorder_requested.emit(self.visual_order())

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt override
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Left:
                self.move_selected("left")
                return
            if event.key() == Qt.Key.Key_Right:
                self.move_selected("right")
                return
        super().keyPressEvent(event)

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
        menu.addAction(f"Move {noun} left  (Ctrl+←)",
                       lambda: self.move_selected("left"))
        menu.addAction(f"Move {noun} right  (Ctrl+→)",
                       lambda: self.move_selected("right"))
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
    page_activated = pyqtSignal(int)

    def __init__(self) -> None:
        super().__init__()

        self._placeholder = self._build_placeholder()

        self._grid = _Grid()
        self._grid.reorder_requested.connect(self.reorder_requested)
        self._grid.rotate_requested.connect(self.rotate_requested)
        self._grid.delete_requested.connect(self.delete_requested)
        self._grid.extract_requested.connect(self.extract_requested)
        self._grid.page_activated.connect(self.page_activated)

        self.addWidget(self._placeholder)
        self.addWidget(self._grid)
        self.setCurrentWidget(self._placeholder)

    @staticmethod
    def _build_placeholder() -> QWidget:
        host = QWidget()
        layout = QVBoxLayout(host)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(18)

        logo = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        logo_path = resource_path("stacked-dark.png")
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path)).scaledToWidth(
                220, Qt.TransformationMode.SmoothTransformation)
            logo.setPixmap(pixmap)
        else:
            logo.setText("Papyrik")
            logo.setStyleSheet("font-size: 28px; font-weight: 700;")

        caption = QLabel("Open a PDF to begin — File ▸ Open…  (Ctrl+O)",
                         alignment=Qt.AlignmentFlag.AlignCenter)
        caption.setStyleSheet("color: #948FAE; font-size: 14px;")

        layout.addWidget(logo)
        layout.addWidget(caption)
        return host

    # -- population -------------------------------------------------------

    def set_page_count(self, count: int) -> None:
        """Reset the grid to `count` numbered placeholder items."""
        self._grid.clear()
        size_hint = self._grid.item_size_hint()
        for i in range(count):
            item = QListWidgetItem(f"Page {i + 1}")
            item.setData(_PAGE_ROLE, i)
            item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
            item.setSizeHint(size_hint)
            self._grid.addItem(item)
        self.setCurrentWidget(self._grid if count else self._placeholder)

    # -- zoom (delegated to the grid) -------------------------------------

    def zoom_in(self) -> None:
        self._grid.zoom_in()

    def zoom_out(self) -> None:
        self._grid.zoom_out()

    def reset_zoom(self) -> None:
        self._grid.reset_zoom()

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

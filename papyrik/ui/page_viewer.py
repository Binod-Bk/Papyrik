"""Full-page viewer - opens on double-click to see a page at readable size.

Renders one page at a time at a higher DPI than the thumbnail grid, with
previous/next navigation and zoom. Sticky-note icons are clickable: click one to
read its text (a page render only shows the icon, not the note's content).
Rendering a single page is fast, so it runs inline; the dialog opens its own
PdfDocument handle and closes it on exit.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from papyrik.core.document import PdfDocument

_ZOOMS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0]
_BASE_DPI = 110
_NOTE_HIT_PAD = 10  # PDF points of slack around a note icon when clicking


class _ClickableImage(QLabel):
    """A QLabel that reports where it was clicked (in pixmap pixels)."""

    clicked = pyqtSignal(QPointF)

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        self.clicked.emit(event.position())


class PageViewer(QDialog):
    def __init__(self, path: str | Path, index: int, count: int,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doc = PdfDocument(path)
        self._index = index
        self._count = count
        self._zoom = 2  # index into _ZOOMS -> 1.0
        self._notes: list[tuple[tuple, str]] = []

        self.setWindowTitle(Path(path).name)
        self.resize(760, 900)

        self._image = _ClickableImage(alignment=Qt.AlignmentFlag.AlignCenter)
        self._image.clicked.connect(self._on_image_click)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self._image)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._prev = QPushButton("‹ Prev")
        self._next = QPushButton("Next ›")
        self._zoom_out = QPushButton("−")
        self._zoom_in = QPushButton("+")
        self._label = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)

        self._prev.clicked.connect(lambda: self._go(-1))
        self._next.clicked.connect(lambda: self._go(1))
        self._zoom_out.clicked.connect(lambda: self._adjust_zoom(-1))
        self._zoom_in.clicked.connect(lambda: self._adjust_zoom(1))

        bar = QHBoxLayout()
        bar.addWidget(self._prev)
        bar.addWidget(self._next)
        bar.addStretch(1)
        bar.addWidget(self._zoom_out)
        bar.addWidget(self._label)
        bar.addWidget(self._zoom_in)

        self._notes_hint = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        self._notes_hint.setStyleSheet("color: palette(mid);")

        layout = QVBoxLayout(self)
        layout.addLayout(bar)
        layout.addWidget(scroll, 1)
        layout.addWidget(self._notes_hint)

        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._go(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._go(1))
        QShortcut(QKeySequence.StandardKey.ZoomIn, self, lambda: self._adjust_zoom(1))
        QShortcut(QKeySequence.StandardKey.ZoomOut, self, lambda: self._adjust_zoom(-1))

        self._render()

    def _go(self, delta: int) -> None:
        new = self._index + delta
        if 0 <= new < self._count:
            self._index = new
            self._render()

    def _adjust_zoom(self, delta: int) -> None:
        new = self._zoom + delta
        if 0 <= new < len(_ZOOMS):
            self._zoom = new
            self._render()

    def _scale(self) -> float:
        return _BASE_DPI * _ZOOMS[self._zoom] / 72.0  # pixels per PDF point

    def _render(self) -> None:
        dpi = int(_BASE_DPI * _ZOOMS[self._zoom])
        data = self._doc.render_png(self._index, dpi=dpi)
        image = QImage()
        image.loadFromData(data, "PNG")
        self._image.setPixmap(QPixmap.fromImage(image))
        self._image.adjustSize()
        self._notes = self._doc.text_notes(self._index)

        self._label.setText(
            f"Page {self._index + 1} / {self._count}   ·   "
            f"{int(_ZOOMS[self._zoom] * 100)}%"
        )
        n = len(self._notes)
        self._notes_hint.setText(
            f"🗨 {n} sticky note{'s' if n != 1 else ''} on this page — "
            "click a note icon to read it." if n else ""
        )
        self._prev.setEnabled(self._index > 0)
        self._next.setEnabled(self._index < self._count - 1)
        self._zoom_out.setEnabled(self._zoom > 0)
        self._zoom_in.setEnabled(self._zoom < len(_ZOOMS) - 1)

    def _on_image_click(self, pos: QPointF) -> None:
        note = self._note_at(pos)
        if note is not None:
            QMessageBox.information(self, "Sticky note",
                                    note or "(empty note)")

    def _note_at(self, pos: QPointF) -> str | None:
        """Return the text of a note whose icon was clicked, else None."""
        scale = self._scale()
        px, py = pos.x() / scale, pos.y() / scale
        for (x0, y0, x1, y1), content in self._notes:
            if (x0 - _NOTE_HIT_PAD <= px <= x1 + _NOTE_HIT_PAD
                    and y0 - _NOTE_HIT_PAD <= py <= y1 + _NOTE_HIT_PAD):
                return content
        return None

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._doc.close()
        super().closeEvent(event)

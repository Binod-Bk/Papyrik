"""Interactive annotation canvas.

Renders one page and lets the user add highlights (drag a box), sticky notes
(click) and freehand ink (drag). Annotations are collected as an overlay and
returned in PDF coordinates; MainWindow applies them in one pass via
annotate.apply_all so the whole session is a single undoable version.
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from papyrik.core.document import PdfDocument

_RENDER_DPI = 130
_HL_FILL = QColor(255, 230, 80, 90)
_INK_PEN = QColor(210, 30, 30)
_NOTE_COLOR = QColor(240, 200, 60)


class _Canvas(QWidget):
    """Paints the page plus the pending annotation overlay and captures input."""

    def __init__(self, pixmap: QPixmap) -> None:
        super().__init__()
        self._pixmap = pixmap
        self.setFixedSize(pixmap.size())
        self.setMouseTracking(True)

        self.tool = "draw"                       # draw | highlight | note
        self.highlights: list[QRectF] = []       # screen coords
        self.strokes: list[list[QPointF]] = []    # screen coords
        self.notes: list[tuple[QPointF, str]] = []
        self._stroke: list[QPointF] | None = None
        self._box_start: QPointF | None = None
        self._box_cur: QPointF | None = None

    # -- painting ---------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.drawPixmap(0, 0, self._pixmap)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_HL_FILL)
        for rect in self.highlights:
            painter.drawRect(rect)
        if self._box_start and self._box_cur:
            painter.drawRect(QRectF(self._box_start, self._box_cur).normalized())

        pen = QPen(_INK_PEN, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for stroke in self.strokes:
            self._draw_polyline(painter, stroke)
        if self._stroke:
            self._draw_polyline(painter, self._stroke)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_NOTE_COLOR)
        for point, _text in self.notes:
            painter.drawRect(QRectF(point.x() - 6, point.y() - 6, 12, 12))

    @staticmethod
    def _draw_polyline(painter: QPainter, pts: list[QPointF]) -> None:
        for i in range(1, len(pts)):
            painter.drawLine(pts[i - 1], pts[i])

    # -- input ------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        pos = QPointF(event.position())
        if self.tool == "draw":
            self._stroke = [pos]
        elif self.tool == "highlight":
            self._box_start = pos
            self._box_cur = pos
        elif self.tool == "note":
            text, ok = QInputDialog.getMultiLineText(
                self, "Sticky note", "Note text:")
            if ok and text.strip():
                self.notes.append((pos, text))
                self.update()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        pos = QPointF(event.position())
        if self.tool == "draw" and self._stroke is not None:
            self._stroke.append(pos)
            self.update()
        elif self.tool == "highlight" and self._box_start is not None:
            self._box_cur = pos
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        pos = QPointF(event.position())
        if self.tool == "draw" and self._stroke is not None:
            if len(self._stroke) >= 2:
                self.strokes.append(self._stroke)
            self._stroke = None
            self.update()
        elif self.tool == "highlight" and self._box_start is not None:
            rect = QRectF(self._box_start, pos).normalized()
            if rect.width() > 3 and rect.height() > 3:
                self.highlights.append(rect)
            self._box_start = self._box_cur = None
            self.update()

    def clear(self) -> None:
        self.highlights.clear()
        self.strokes.clear()
        self.notes.clear()
        self._stroke = None
        self._box_start = self._box_cur = None
        self.update()


class AnnotationView(QDialog):
    def __init__(self, path: str | Path, page: int, tool: str = "draw",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = page
        self._scale = _RENDER_DPI / 72.0
        self.setWindowTitle(f"Annotate — page {page + 1}")

        with PdfDocument(path) as doc:
            data = doc.render_png(page, dpi=_RENDER_DPI)
        image = QImage()
        image.loadFromData(data, "PNG")
        self._canvas = _Canvas(QPixmap.fromImage(image))
        self._canvas.tool = tool

        scroll = QScrollArea()
        scroll.setWidget(self._canvas)
        scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)

        toolbar = QHBoxLayout()
        self._group = QButtonGroup(self)
        for name, label in (("highlight", "Highlight"), ("note", "Sticky Note"),
                            ("draw", "Draw")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(name == tool)
            button.clicked.connect(lambda _c, n=name: self._set_tool(n))
            self._group.addButton(button)
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        clear = QPushButton("Clear")
        clear.clicked.connect(self._canvas.clear)
        toolbar.addWidget(clear)

        hint = QLabel("Highlight/Draw: drag on the page.  Sticky Note: click.")
        hint.setStyleSheet("color: palette(mid);")

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Apply
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(
            self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(scroll, 1)
        layout.addWidget(hint)
        layout.addWidget(buttons)
        self.resize(min(self._canvas.width() + 60, 1000),
                    min(self._canvas.height() + 140, 900))

    def _set_tool(self, name: str) -> None:
        self._canvas.tool = name

    def result_annotations(self) -> dict:
        """Collected annotations converted to PDF coordinates."""
        s = self._scale

        def pt(p: QPointF) -> tuple[float, float]:
            return (p.x() / s, p.y() / s)

        highlights = [(r.left() / s, r.top() / s, r.right() / s, r.bottom() / s)
                      for r in self._canvas.highlights]
        notes = [(pt(p), text) for p, text in self._canvas.notes]
        strokes = [[pt(p) for p in stroke] for stroke in self._canvas.strokes]
        return {"highlights": highlights, "notes": notes, "strokes": strokes}

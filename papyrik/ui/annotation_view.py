"""Interactive annotation canvas.

Renders one page fit-to-window and lets the user add highlights (drag a box),
sticky notes (click) and freehand ink (drag). Annotations are stored in PDF
coordinates, so the page can be freely resized without the marks drifting, and
they're returned as-is to MainWindow, which applies them in one pass via
annotate.apply_all (a single undoable version).
"""

from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import (
    QColor,
    QImage,
    QKeySequence,
    QPainter,
    QPen,
    QPixmap,
    QShortcut,
)
from PyQt6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from papyrik.core.document import PdfDocument

_RENDER_DPI = 150
_INK_PEN = QColor(210, 30, 30)
_NOTE_COLOR = QColor(240, 200, 60)
_PAGE_BORDER = QColor(0, 0, 0, 40)

# Highlighter colours: (name, (r, g, b) in 0-1). First is the default.
_HL_COLORS = [
    ("Yellow", (1.0, 0.90, 0.30)),
    ("Green", (0.55, 0.92, 0.50)),
    ("Pink", (1.0, 0.60, 0.78)),
    ("Blue", (0.50, 0.78, 1.0)),
    ("Orange", (1.0, 0.72, 0.30)),
]


def _fill(rgb: tuple, alpha: int = 90) -> QColor:
    return QColor(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255), alpha)


class _Canvas(QWidget):
    """Draws the page scaled-to-fit plus the pending overlay; captures input.

    All stored coordinates are in PDF points. Screen<->PDF conversion uses the
    display transform computed fresh each paint, so resizing the window never
    invalidates existing annotations.
    """

    def __init__(self, base: QPixmap, page_w: float, page_h: float) -> None:
        super().__init__()
        self._base = base
        self._pw = page_w
        self._ph = page_h
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(300, 300)
        self.setMouseTracking(True)

        self.tool = "draw"                          # draw | highlight | note
        self.hl_color = _HL_COLORS[0][1]            # current highlighter colour
        self.highlights: list[tuple[QRectF, tuple]] = []  # (rect, rgb) PDF coords
        self.strokes: list[list[QPointF]] = []       # PDF coords
        self.notes: list[tuple[QPointF, str]] = []    # PDF coords
        self._order: list[str] = []                  # for last-in undo
        self._stroke: list[QPointF] | None = None
        self._box_start: QPointF | None = None
        self._box_cur: QPointF | None = None

    # -- display transform ------------------------------------------------

    def _disp(self) -> tuple[float, float, float]:
        scale = min(self.width() / self._pw, self.height() / self._ph)
        off_x = (self.width() - self._pw * scale) / 2
        off_y = (self.height() - self._ph * scale) / 2
        return scale, off_x, off_y

    def _to_screen(self, x: float, y: float) -> QPointF:
        scale, ox, oy = self._disp()
        return QPointF(x * scale + ox, y * scale + oy)

    def _to_pdf(self, sx: float, sy: float) -> QPointF:
        scale, ox, oy = self._disp()
        x = min(max((sx - ox) / scale, 0.0), self._pw)
        y = min(max((sy - oy) / scale, 0.0), self._ph)
        return QPointF(x, y)

    # -- painting ---------------------------------------------------------

    def paintEvent(self, _event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        scale, ox, oy = self._disp()
        target = QRectF(ox, oy, self._pw * scale, self._ph * scale)
        painter.drawPixmap(target, self._base, QRectF(self._base.rect()))
        painter.setPen(QPen(_PAGE_BORDER, 1))
        painter.drawRect(target)

        painter.setPen(Qt.PenStyle.NoPen)
        for rect, color in self.highlights:
            painter.setBrush(_fill(color))
            painter.drawRect(self._rect_to_screen(rect))
        if self._box_start and self._box_cur:
            painter.setBrush(_fill(self.hl_color))
            painter.drawRect(QRectF(self._to_screen(self._box_start.x(),
                                                    self._box_start.y()),
                                    self._to_screen(self._box_cur.x(),
                                                    self._box_cur.y())))

        pen = QPen(_INK_PEN, 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for stroke in self.strokes:
            self._draw_stroke(painter, stroke)
        if self._stroke:
            self._draw_stroke(painter, self._stroke)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(_NOTE_COLOR)
        for point, _text in self.notes:
            s = self._to_screen(point.x(), point.y())
            painter.drawRect(QRectF(s.x() - 6, s.y() - 6, 12, 12))

    def _rect_to_screen(self, r: QRectF) -> QRectF:
        return QRectF(self._to_screen(r.left(), r.top()),
                      self._to_screen(r.right(), r.bottom()))

    def _draw_stroke(self, painter: QPainter, pts: list[QPointF]) -> None:
        screen = [self._to_screen(p.x(), p.y()) for p in pts]
        for i in range(1, len(screen)):
            painter.drawLine(screen[i - 1], screen[i])

    # -- input ------------------------------------------------------------

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt override
        pos = self._to_pdf(event.position().x(), event.position().y())
        if self.tool == "draw":
            self._stroke = [pos]
        elif self.tool == "highlight":
            self._box_start = pos
            self._box_cur = pos
        elif self.tool == "note":
            hit = self._note_at(pos)
            if hit is not None:  # click an existing note -> view/edit its text
                text, ok = QInputDialog.getMultiLineText(
                    self, "Sticky note", "Note text:", self.notes[hit][1])
                if ok and text.strip():
                    self.notes[hit] = (self.notes[hit][0], text)
                    self.update()
                return
            text, ok = QInputDialog.getMultiLineText(
                self, "Sticky note", "Note text:")
            if ok and text.strip():
                self.notes.append((pos, text))
                self._order.append("note")
                self.update()

    def _note_at(self, pdf_point: QPointF) -> int | None:
        """Index of an existing note within a few pixels of `pdf_point`."""
        scale = self._disp()[0]
        tol = 9 / scale if scale else 9
        for i, (point, _text) in enumerate(self.notes):
            if (abs(point.x() - pdf_point.x()) <= tol
                    and abs(point.y() - pdf_point.y()) <= tol):
                return i
        return None

    def mouseMoveEvent(self, event) -> None:  # noqa: N802 - Qt override
        pos = self._to_pdf(event.position().x(), event.position().y())
        if self.tool == "draw" and self._stroke is not None:
            self._stroke.append(pos)
            self.update()
        elif self.tool == "highlight" and self._box_start is not None:
            self._box_cur = pos
            self.update()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt override
        pos = self._to_pdf(event.position().x(), event.position().y())
        if self.tool == "draw" and self._stroke is not None:
            if len(self._stroke) >= 2:
                self.strokes.append(self._stroke)
                self._order.append("stroke")
            self._stroke = None
            self.update()
        elif self.tool == "highlight" and self._box_start is not None:
            rect = QRectF(self._box_start, pos).normalized()
            if rect.width() > 2 and rect.height() > 2:
                self.highlights.append((rect, self.hl_color))
                self._order.append("highlight")
            self._box_start = self._box_cur = None
            self.update()

    # -- edit -------------------------------------------------------------

    def undo(self) -> None:
        if not self._order:
            return
        kind = self._order.pop()
        {"highlight": self.highlights, "note": self.notes,
         "stroke": self.strokes}[kind].pop()
        self.update()

    def clear(self) -> None:
        self.highlights.clear()
        self.strokes.clear()
        self.notes.clear()
        self._order.clear()
        self._stroke = None
        self._box_start = self._box_cur = None
        self.update()


class AnnotationView(QDialog):
    def __init__(self, path: str | Path, page: int, tool: str = "draw",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.page = page
        self.setWindowTitle(f"Annotate — page {page + 1}")

        with PdfDocument(path) as doc:
            data = doc.render_png(page, dpi=_RENDER_DPI)
        image = QImage()
        image.loadFromData(data, "PNG")
        page_w = image.width() * 72.0 / _RENDER_DPI
        page_h = image.height() * 72.0 / _RENDER_DPI
        self._canvas = _Canvas(QPixmap.fromImage(image), page_w, page_h)
        self._canvas.tool = tool

        toolbar = QHBoxLayout()
        self._buttons: dict[str, QPushButton] = {}
        for name, label in (("highlight", "Highlight"), ("note", "Sticky Note"),
                            ("draw", "Draw")):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(name == tool)
            button.clicked.connect(lambda _c, n=name: self._set_tool(n))
            self._buttons[name] = button
            toolbar.addWidget(button)

        toolbar.addSpacing(12)
        self._swatches = QButtonGroup(self)
        for i, (cname, rgb) in enumerate(_HL_COLORS):
            swatch = QPushButton()
            swatch.setFixedSize(22, 22)
            swatch.setCheckable(True)
            swatch.setChecked(i == 0)
            swatch.setToolTip(f"Highlight colour: {cname}")
            hexc = "#%02X%02X%02X" % (int(rgb[0] * 255), int(rgb[1] * 255),
                                      int(rgb[2] * 255))
            swatch.setStyleSheet(
                f"QPushButton{{background:{hexc};border-radius:4px;"
                "border:2px solid #00000000;}"
                "QPushButton:checked{border:2px solid #FFFFFF;}")
            swatch.clicked.connect(lambda _c, c=rgb: self._set_hl_color(c))
            self._swatches.addButton(swatch)
            toolbar.addWidget(swatch)

        toolbar.addStretch(1)
        undo = QPushButton("Undo (Ctrl+Z)")
        undo.clicked.connect(self._canvas.undo)
        clear = QPushButton("Clear all")
        clear.clicked.connect(self._canvas.clear)
        toolbar.addWidget(undo)
        toolbar.addWidget(clear)
        toolbar.addSpacing(16)
        # Primary actions live in the always-visible top bar so they're never
        # pushed off-screen on shorter displays.
        apply_btn = QPushButton("Apply && Save")
        apply_btn.setDefault(True)
        apply_btn.setStyleSheet("font-weight: 600; padding: 4px 14px;")
        apply_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        toolbar.addWidget(apply_btn)
        toolbar.addWidget(cancel_btn)

        hint = QLabel("Highlight / Draw: drag on the page.   Sticky Note: click "
                      "an empty spot to add, or an existing note to edit.")
        hint.setStyleSheet("color: palette(mid);")

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self._canvas, 1)
        layout.addWidget(hint)
        self.resize(940, 720)

        QShortcut(QKeySequence.StandardKey.Undo, self, self._canvas.undo)

    def _set_tool(self, name: str) -> None:
        self._canvas.tool = name
        for key, button in self._buttons.items():
            button.setChecked(key == name)

    def _set_hl_color(self, rgb: tuple) -> None:
        self._canvas.hl_color = rgb

    def result_annotations(self) -> dict:
        """Collected annotations, already in PDF coordinates."""
        highlights = [((r.left(), r.top(), r.right(), r.bottom()), color)
                      for r, color in self._canvas.highlights]
        notes = [((p.x(), p.y()), text) for p, text in self._canvas.notes]
        strokes = [[(p.x(), p.y()) for p in stroke]
                   for stroke in self._canvas.strokes]
        return {"highlights": highlights, "notes": notes, "strokes": strokes}

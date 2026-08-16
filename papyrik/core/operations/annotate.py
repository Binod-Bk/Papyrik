"""Annotations: highlight, sticky note, freehand draw.

Pure functions - paths + coordinates in, an output path out; the input file is
never modified. Coordinates are in PDF points (origin top-left, as PyMuPDF
reports page.rect); the UI converts from screen coordinates before calling in.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

# (r, g, b) in 0-1, matching a translucent yellow highlighter by default.
_HIGHLIGHT_RGB = (1.0, 0.9, 0.3)
_INK_RGB = (0.85, 0.1, 0.1)


def _open_pdf(path: str | Path) -> pymupdf.Document:
    doc = pymupdf.open(str(path))
    if doc.needs_pass:
        doc.close()
        raise ValueError(
            f"'{Path(path).name}' is password-protected; decrypt it first."
        )
    return doc


def _save(doc: pymupdf.Document, output: str | Path) -> Path:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out), garbage=3, deflate=True)
    return out


def _page(doc: pymupdf.Document, index: int) -> pymupdf.Page:
    if not 0 <= index < doc.page_count:
        raise IndexError(f"Page {index} out of range (0..{doc.page_count - 1}).")
    return doc[index]


def highlight(input_pdf: str | Path, page: int, rects: list[tuple],
              output: str | Path) -> Path:
    """Highlight the given rectangles (x0, y0, x1, y1) on `page`."""
    if not rects:
        raise ValueError("highlight needs at least one rectangle.")
    doc = _open_pdf(input_pdf)
    try:
        pg = _page(doc, page)
        for rect in rects:
            annot = pg.add_highlight_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=_HIGHLIGHT_RGB)
            annot.update()
        return _save(doc, output)
    finally:
        doc.close()


def text_note(input_pdf: str | Path, page: int, point: tuple, text: str,
              output: str | Path) -> Path:
    """Add a sticky-note annotation at `point` (x, y) on `page`."""
    if not text:
        raise ValueError("text_note needs non-empty text.")
    doc = _open_pdf(input_pdf)
    try:
        pg = _page(doc, page)
        pg.add_text_annot(pymupdf.Point(point), text)
        return _save(doc, output)
    finally:
        doc.close()


def draw(input_pdf: str | Path, page: int, strokes: list[list[tuple]],
         output: str | Path) -> Path:
    """Add freehand ink `strokes` on `page`.

    `strokes` is a list of strokes; each stroke is a list of (x, y) points.
    """
    strokes = [s for s in strokes if len(s) >= 2]
    if not strokes:
        raise ValueError("draw needs at least one stroke of two or more points.")
    doc = _open_pdf(input_pdf)
    try:
        pg = _page(doc, page)
        _add_ink(pg, strokes)
        return _save(doc, output)
    finally:
        doc.close()


def apply_all(input_pdf: str | Path, output: str | Path, page: int, *,
              highlights: list[tuple] | None = None,
              notes: list[tuple] | None = None,
              strokes: list[list[tuple]] | None = None) -> Path:
    """Apply a full annotation session (any mix) to `page` in one pass.

    Lets the UI turn a whole session into a single undoable document version.
    """
    highlights = highlights or []
    notes = notes or []
    strokes = [s for s in (strokes or []) if len(s) >= 2]
    if not (highlights or notes or strokes):
        raise ValueError("apply_all needs at least one annotation.")
    doc = _open_pdf(input_pdf)
    try:
        pg = _page(doc, page)
        for rect in highlights:
            annot = pg.add_highlight_annot(pymupdf.Rect(rect))
            annot.set_colors(stroke=_HIGHLIGHT_RGB)
            annot.update()
        for point, text in notes:
            if text:
                pg.add_text_annot(pymupdf.Point(point), text)
        if strokes:
            _add_ink(pg, strokes)
        return _save(doc, output)
    finally:
        doc.close()


def _add_ink(page: pymupdf.Page, strokes: list[list[tuple]]) -> None:
    annot = page.add_ink_annot(strokes)
    annot.set_colors(stroke=_INK_RGB)
    annot.set_border(width=1.5)
    annot.update()

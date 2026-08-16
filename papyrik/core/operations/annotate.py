"""Annotations: highlight, sticky note, freehand draw. Implemented day 3."""

from __future__ import annotations

from pathlib import Path


def highlight(input_pdf: str | Path, page: int, rects: list[tuple],
              output: str | Path) -> Path:
    """Highlight the given rectangles on `page`."""
    raise NotImplementedError


def text_note(input_pdf: str | Path, page: int, point: tuple, text: str,
              output: str | Path) -> Path:
    """Add a sticky-note annotation at `point` on `page`."""
    raise NotImplementedError


def draw(input_pdf: str | Path, page: int, strokes: list[list[tuple]],
         output: str | Path) -> Path:
    """Add freehand ink `strokes` on `page`."""
    raise NotImplementedError

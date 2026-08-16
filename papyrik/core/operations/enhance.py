"""Enhance: compress, watermark, page_numbers. Implemented day 2."""

from __future__ import annotations

from pathlib import Path


def compress(input_pdf: str | Path, output: str | Path,
             preset: str = "balanced") -> Path:
    """Reduce file size. `preset` is one of low/balanced/high quality."""
    raise NotImplementedError


def watermark(input_pdf: str | Path, output: str | Path, *,
              text: str | None = None, image: str | Path | None = None,
              opacity: float = 0.3, rotation: int = 45,
              position: str = "center") -> Path:
    """Stamp a text or image watermark on every page."""
    raise NotImplementedError


def page_numbers(input_pdf: str | Path, output: str | Path, *,
                 start: int = 1, position: str = "bottom-center") -> Path:
    """Stamp page numbers."""
    raise NotImplementedError

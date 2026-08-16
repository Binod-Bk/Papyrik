"""Conversions: pdf->docx, pdf->images, images->pdf, pdf->text.

Pure functions. `pdf_to_docx` is best-effort on multi-column/table layouts
(see CLAUDE.md "Known-flaky"). Implemented day 2.
"""

from __future__ import annotations

from pathlib import Path


def pdf_to_docx(input_pdf: str | Path, output: str | Path) -> Path:
    """Convert to Word. Best effort on complex layouts."""
    raise NotImplementedError


def pdf_to_images(input_pdf: str | Path, output_dir: str | Path,
                  fmt: str = "png", dpi: int = 150) -> list[Path]:
    """Render each page to an image file."""
    raise NotImplementedError


def images_to_pdf(images: list[str | Path], output: str | Path) -> Path:
    """Combine images into a single PDF, one image per page."""
    raise NotImplementedError


def pdf_to_text(input_pdf: str | Path, output: str | Path) -> Path:
    """Extract the text layer to a .txt file."""
    raise NotImplementedError

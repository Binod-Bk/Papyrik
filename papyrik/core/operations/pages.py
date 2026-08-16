"""Page operations: merge, split, rotate, delete, extract, reorder.

Pure functions — paths + params in, an output path out. Never mutate the
input file. Implemented in the page-ops prompt (day 1).
"""

from __future__ import annotations

from pathlib import Path


def merge(inputs: list[str | Path], output: str | Path) -> Path:
    """Concatenate `inputs` into a single PDF at `output`."""
    raise NotImplementedError


def split_by_range(input_pdf: str | Path, ranges: list[tuple[int, int]],
                   output_dir: str | Path) -> list[Path]:
    """Split `input_pdf` into one file per (start, end) page range."""
    raise NotImplementedError


def split_every_n(input_pdf: str | Path, n: int,
                  output_dir: str | Path) -> list[Path]:
    """Split `input_pdf` into chunks of `n` pages each."""
    raise NotImplementedError


def rotate(input_pdf: str | Path, pages: list[int], degrees: int,
           output: str | Path) -> Path:
    """Rotate the given 0-based `pages` by `degrees` (90/180/270)."""
    raise NotImplementedError


def delete_pages(input_pdf: str | Path, pages: list[int],
                 output: str | Path) -> Path:
    """Remove the given 0-based `pages`."""
    raise NotImplementedError


def extract_pages(input_pdf: str | Path, pages: list[int],
                  output: str | Path) -> Path:
    """Save the given 0-based `pages` as a new PDF."""
    raise NotImplementedError


def reorder(input_pdf: str | Path, order: list[int],
            output: str | Path) -> Path:
    """Reorder pages to match `order` (a full permutation of page indices)."""
    raise NotImplementedError

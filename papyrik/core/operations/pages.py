"""Page operations: merge, split, rotate, delete, extract, reorder.

Pure functions - paths + params in, an output path out. They never mutate the
input file (pypdf reads into memory and writes a fresh file). All page indices
are **0-based**; ranges are inclusive. The UI translates from 1-based page
numbers before calling in.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader, PdfWriter


def _reader(path: str | Path) -> PdfReader:
    reader = PdfReader(str(path))
    if reader.is_encrypted:
        # An empty-password decrypt succeeds for files with no user password;
        # otherwise the caller must decrypt first (see operations.security).
        if reader.decrypt("") == 0:
            raise ValueError(
                f"'{Path(path).name}' is password-protected; decrypt it first."
            )
    return reader


def _write(writer: PdfWriter, output: str | Path) -> Path:
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fh:
        writer.write(fh)
    return out


def _check_indices(pages: list[int], count: int) -> None:
    for p in pages:
        if not 0 <= p < count:
            raise IndexError(f"Page {p} out of range (0..{count - 1}).")


def merge(inputs: list[str | Path], output: str | Path) -> Path:
    """Concatenate `inputs` (in order) into a single PDF at `output`."""
    if not inputs:
        raise ValueError("merge needs at least one input file.")
    writer = PdfWriter()
    for inp in inputs:
        for page in _reader(inp).pages:
            writer.add_page(page)
    return _write(writer, output)


def split_by_range(input_pdf: str | Path, ranges: list[tuple[int, int]],
                   output_dir: str | Path) -> list[Path]:
    """Write one file per inclusive, 0-based (start, end) page range."""
    if not ranges:
        raise ValueError("split_by_range needs at least one range.")
    reader = _reader(input_pdf)
    count = len(reader.pages)
    stem = Path(input_pdf).stem
    out_dir = Path(output_dir)
    outputs: list[Path] = []
    for k, (start, end) in enumerate(ranges, start=1):
        if start > end:
            raise ValueError(f"Range start {start} is after end {end}.")
        _check_indices([start, end], count)
        writer = PdfWriter()
        for i in range(start, end + 1):
            writer.add_page(reader.pages[i])
        outputs.append(_write(writer, out_dir / f"{stem}_part{k}.pdf"))
    return outputs


def split_every_n(input_pdf: str | Path, n: int,
                  output_dir: str | Path) -> list[Path]:
    """Split into chunks of `n` pages each."""
    if n < 1:
        raise ValueError("n must be >= 1.")
    reader = _reader(input_pdf)
    total = len(reader.pages)
    stem = Path(input_pdf).stem
    out_dir = Path(output_dir)
    outputs: list[Path] = []
    for part, start in enumerate(range(0, total, n), start=1):
        writer = PdfWriter()
        for i in range(start, min(start + n, total)):
            writer.add_page(reader.pages[i])
        outputs.append(_write(writer, out_dir / f"{stem}_part{part}.pdf"))
    return outputs


def rotate(input_pdf: str | Path, pages: list[int], degrees: int,
           output: str | Path) -> Path:
    """Rotate the given 0-based `pages` by `degrees` (a multiple of 90)."""
    if degrees % 90 != 0:
        raise ValueError("degrees must be a multiple of 90.")
    reader = _reader(input_pdf)
    _check_indices(pages, len(reader.pages))
    targets = set(pages)
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in targets:
            page.rotate(degrees)
        writer.add_page(page)
    return _write(writer, output)


def delete_pages(input_pdf: str | Path, pages: list[int],
                 output: str | Path) -> Path:
    """Remove the given 0-based `pages`."""
    if not pages:
        raise ValueError("delete_pages needs at least one page.")
    reader = _reader(input_pdf)
    count = len(reader.pages)
    _check_indices(pages, count)
    drop = set(pages)
    if len(drop) >= count:
        raise ValueError("Cannot delete every page.")
    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i not in drop:
            writer.add_page(page)
    return _write(writer, output)


def extract_pages(input_pdf: str | Path, pages: list[int],
                  output: str | Path) -> Path:
    """Save the given 0-based `pages` as a new PDF, in ascending order."""
    if not pages:
        raise ValueError("extract_pages needs at least one page.")
    reader = _reader(input_pdf)
    _check_indices(pages, len(reader.pages))
    writer = PdfWriter()
    for i in sorted(set(pages)):
        writer.add_page(reader.pages[i])
    return _write(writer, output)


def reorder(input_pdf: str | Path, order: list[int],
            output: str | Path) -> Path:
    """Reorder pages to match `order` - a full permutation of page indices."""
    reader = _reader(input_pdf)
    count = len(reader.pages)
    if sorted(order) != list(range(count)):
        raise ValueError(
            f"order must be a permutation of 0..{count - 1}."
        )
    writer = PdfWriter()
    for idx in order:
        writer.add_page(reader.pages[idx])
    return _write(writer, output)

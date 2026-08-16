"""Batch runner - apply one operation to every PDF in a folder.

Kept generic and pure: the caller passes an already-bound operation
`op(input_path, output_path)`; batch just walks the folder, names outputs, and
collects a per-file result. One bad file never aborts the run - corrupt PDFs are
normal, so their error is recorded and the batch continues.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

# One result per input file: (input, output or None if it failed, error or None).
BatchResult = tuple[Path, Optional[Path], Optional[str]]


def run_batch(folder: str | Path, operation: Callable[[str, str], object],
              output_dir: str | Path, *, ext: str = "pdf", suffix: str = "",
              progress: Callable[[int, int], None] | None = None,
              ) -> list[BatchResult]:
    """Run `operation` over every *.pdf in `folder`, writing to `output_dir`.

    `suffix`/`ext` build each output name as "<stem><suffix>.<ext>". A progress
    callback, if given, is called as progress(done, total) after each file.
    """
    folder = Path(folder)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(p for p in folder.glob("*.pdf") if p.is_file())
    total = len(pdfs)
    results: list[BatchResult] = []
    for i, pdf in enumerate(pdfs, start=1):
        out = output_dir / f"{pdf.stem}{suffix}.{ext}"
        if out.resolve() == pdf.resolve():
            results.append((pdf, None, "output would overwrite the input file"))
        else:
            try:
                operation(str(pdf), str(out))
                results.append((pdf, out, None))
            except Exception as exc:  # corrupt/odd files are expected
                results.append((pdf, None, str(exc)))
        if progress is not None:
            progress(i, total)
    return results

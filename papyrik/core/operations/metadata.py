"""Document metadata: read and write the standard Info fields.

Pure functions - the input file is never modified; writes go to a new path.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

# Editable Info fields exposed in the UI.
FIELDS = ["title", "author", "subject", "keywords", "creator", "producer"]


def _open_pdf(path: str | Path) -> pymupdf.Document:
    doc = pymupdf.open(str(path))
    if doc.needs_pass:
        doc.close()
        raise ValueError(
            f"'{Path(path).name}' is password-protected; decrypt it first."
        )
    return doc


def read_metadata(input_pdf: str | Path) -> dict[str, str]:
    """Return the editable Info fields (missing values as empty strings)."""
    doc = _open_pdf(input_pdf)
    try:
        meta = doc.metadata or {}
        return {field: (meta.get(field) or "") for field in FIELDS}
    finally:
        doc.close()


def write_metadata(input_pdf: str | Path, output: str | Path,
                   values: dict[str, str]) -> Path:
    """Write a copy of `input_pdf` with the given Info fields updated.

    Only keys in FIELDS are applied; other metadata (dates, trapped) is kept.
    """
    doc = _open_pdf(input_pdf)
    try:
        meta = dict(doc.metadata or {})
        meta.pop("format", None)      # not part of the writable Info dict
        meta.pop("encryption", None)
        for field in FIELDS:
            if field in values:
                meta[field] = values[field]
        doc.set_metadata(meta)

        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out), garbage=3, deflate=True)
        return out
    finally:
        doc.close()

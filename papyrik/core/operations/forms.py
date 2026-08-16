"""Forms: read and fill existing AcroForm fields (no form creation).

Implemented day 3.
"""

from __future__ import annotations

from pathlib import Path


def read_fields(input_pdf: str | Path) -> dict[str, str]:
    """Return a mapping of existing form field names to current values."""
    raise NotImplementedError


def fill_fields(input_pdf: str | Path, values: dict[str, str],
                output: str | Path) -> Path:
    """Fill existing AcroForm fields with `values`."""
    raise NotImplementedError

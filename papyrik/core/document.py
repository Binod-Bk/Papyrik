"""PdfDocument — the single source of truth for an open file.

Scaffold: signature and docstrings only. Implemented in the document-core
prompt (open/close, page count, thumbnail rendering, dirty tracking).
"""

from __future__ import annotations

from pathlib import Path


class PdfDocument:
    """Wraps a PyMuPDF document plus UI-facing state (path, dirty flag)."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        raise NotImplementedError("PdfDocument is implemented in a later prompt.")

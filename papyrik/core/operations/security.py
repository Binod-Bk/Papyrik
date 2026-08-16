"""Security: encrypt, decrypt, permissions. Implemented day 2."""

from __future__ import annotations

from pathlib import Path


def encrypt(input_pdf: str | Path, password: str, output: str | Path) -> Path:
    """Password-protect the PDF."""
    raise NotImplementedError


def decrypt(input_pdf: str | Path, password: str, output: str | Path) -> Path:
    """Remove a known password."""
    raise NotImplementedError

"""Locate bundled assets (logos, icon) in both dev and frozen (PyInstaller) runs."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_path(name: str) -> Path:
    """Absolute path to an asset in assets/, dev or frozen."""
    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) if base else Path(__file__).resolve().parent.parent
    return root / "assets" / name

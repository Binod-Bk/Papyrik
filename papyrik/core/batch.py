"""Batch runner — apply any pure operation to every PDF in a folder.

Scaffold: signature only. Implemented on day 3.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable


def run_batch(
    folder: str | Path,
    operation: Callable[..., Any],
    output_dir: str | Path,
    **params: Any,
) -> list[Path]:
    """Run `operation` over every PDF in `folder`, writing to `output_dir`."""
    raise NotImplementedError("Batch mode is implemented on day 3.")

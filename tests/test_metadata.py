"""Tests for papyrik.core.operations.metadata against the fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from papyrik.core.operations import metadata
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


def test_read_returns_all_fields():
    data = metadata.read_metadata(_fixture("cjk.pdf"))
    assert set(data) == set(metadata.FIELDS)
    assert all(isinstance(v, str) for v in data.values())


def test_write_updates_fields(tmp_path):
    out = metadata.write_metadata(
        _fixture("cjk.pdf"), tmp_path / "m.pdf",
        {"title": "Papyrik Test", "author": "Binod"},
    )
    back = metadata.read_metadata(out)
    assert back["title"] == "Papyrik Test"
    assert back["author"] == "Binod"


def test_write_preserves_pages(tmp_path):
    out = metadata.write_metadata(
        _fixture("large_300p.pdf"), tmp_path / "m.pdf", {"title": "X"}
    )
    assert len(PdfReader(str(out)).pages) == 300


def test_write_does_not_modify_input(tmp_path):
    src = _fixture("cjk.pdf")
    before = src.read_bytes()
    metadata.write_metadata(src, tmp_path / "m.pdf", {"title": "X"})
    assert src.read_bytes() == before


def test_partial_update_keeps_other_fields(tmp_path):
    step1 = metadata.write_metadata(
        _fixture("cjk.pdf"), tmp_path / "a.pdf",
        {"title": "Keep", "author": "Me"},
    )
    step2 = metadata.write_metadata(step1, tmp_path / "b.pdf", {"author": "You"})
    back = metadata.read_metadata(step2)
    assert back["title"] == "Keep"   # untouched
    assert back["author"] == "You"   # updated


def test_read_encrypted_raises():
    with pytest.raises(ValueError):
        metadata.read_metadata(_fixture("encrypted.pdf"))

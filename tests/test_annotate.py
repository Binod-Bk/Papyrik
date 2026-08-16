"""Tests for papyrik.core.operations.annotate against the fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import pymupdf

from papyrik.core.operations import annotate
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


def _annot_types(pdf_path, page=0) -> list[str]:
    with pymupdf.open(str(pdf_path)) as doc:
        return [a.type[1] for a in doc[page].annots()]


# -- highlight -----------------------------------------------------------

def test_highlight_adds_annotation(tmp_path):
    out = annotate.highlight(_fixture("cjk.pdf"), 0,
                             [(72, 90, 300, 130)], tmp_path / "h.pdf")
    assert "Highlight" in _annot_types(out)


def test_highlight_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        annotate.highlight(_fixture("cjk.pdf"), 0, [], tmp_path / "x.pdf")


# -- text note -----------------------------------------------------------

def test_text_note_adds_annotation(tmp_path):
    out = annotate.text_note(_fixture("cjk.pdf"), 0, (100, 100),
                             "Review this", tmp_path / "n.pdf")
    assert "Text" in _annot_types(out)


def test_text_note_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        annotate.text_note(_fixture("cjk.pdf"), 0, (10, 10), "", tmp_path / "x.pdf")


# -- draw ----------------------------------------------------------------

def test_draw_adds_ink(tmp_path):
    strokes = [[(72, 72), (120, 100), (160, 72)]]
    out = annotate.draw(_fixture("cjk.pdf"), 0, strokes, tmp_path / "d.pdf")
    assert "Ink" in _annot_types(out)


def test_draw_drops_degenerate_strokes(tmp_path):
    with pytest.raises(ValueError):
        annotate.draw(_fixture("cjk.pdf"), 0, [[(1, 1)]], tmp_path / "x.pdf")


# -- shared guards -------------------------------------------------------

def test_page_out_of_range(tmp_path):
    with pytest.raises(IndexError):
        annotate.text_note(_fixture("cjk.pdf"), 9, (10, 10), "x", tmp_path / "x.pdf")


def test_encrypted_raises(tmp_path):
    with pytest.raises(ValueError):
        annotate.text_note(_fixture("encrypted.pdf"), 0, (10, 10), "x",
                           tmp_path / "x.pdf")


def test_input_not_modified(tmp_path):
    src = _fixture("cjk.pdf")
    before = src.read_bytes()
    annotate.text_note(src, 0, (10, 10), "x", tmp_path / "n.pdf")
    assert src.read_bytes() == before


# -- apply_all (combined session) ----------------------------------------

def test_apply_all_mixed(tmp_path):
    out = annotate.apply_all(
        _fixture("cjk.pdf"), tmp_path / "a.pdf", 0,
        highlights=[(72, 90, 300, 130)],
        notes=[((100, 200), "see here")],
        strokes=[[(72, 72), (120, 100), (160, 72)]],
    )
    types = _annot_types(out)
    assert "Highlight" in types and "Text" in types and "Ink" in types


def test_apply_all_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        annotate.apply_all(_fixture("cjk.pdf"), tmp_path / "x.pdf", 0)

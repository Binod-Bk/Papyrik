"""Tests for papyrik.core.operations.convert against the fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest

from papyrik.core.operations import convert
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


# -- pdf_to_text ---------------------------------------------------------

def test_pdf_to_text_extracts_layer(tmp_path):
    out = convert.pdf_to_text(_fixture("large_300p.pdf"), tmp_path / "t.txt")
    text = out.read_text(encoding="utf-8")
    assert "Page 1 of 300" in text
    assert "Page 300 of 300" in text


def test_pdf_to_text_encrypted_raises(tmp_path):
    with pytest.raises(ValueError):
        convert.pdf_to_text(_fixture("encrypted.pdf"), tmp_path / "t.txt")


# -- pdf_to_images -------------------------------------------------------

def test_pdf_to_images_png(tmp_path):
    outs = convert.pdf_to_images(_fixture("cjk.pdf"), tmp_path, fmt="png")
    assert len(outs) == 1
    assert outs[0].read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_pdf_to_images_jpg_multipage(tmp_path):
    outs = convert.pdf_to_images(_fixture("large_300p.pdf"), tmp_path,
                                 fmt="jpg", dpi=48)
    assert len(outs) == 300
    assert outs[0].read_bytes()[:3] == b"\xff\xd8\xff"  # JPEG SOI
    # Zero-padded, natural sort order.
    assert outs[0].name.endswith("_p001.jpg")
    assert outs[-1].name.endswith("_p300.jpg")


def test_pdf_to_images_bad_format(tmp_path):
    with pytest.raises(ValueError):
        convert.pdf_to_images(_fixture("cjk.pdf"), tmp_path, fmt="gif")


# -- images_to_pdf -------------------------------------------------------

def test_images_to_pdf_roundtrip(tmp_path):
    imgs = convert.pdf_to_images(_fixture("cjk.pdf"), tmp_path, fmt="png")
    imgs = imgs + imgs  # two pages from the same rendered image
    out = convert.images_to_pdf(imgs, tmp_path / "combined.pdf")

    from pypdf import PdfReader
    assert len(PdfReader(str(out)).pages) == 2


def test_images_to_pdf_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        convert.images_to_pdf([], tmp_path / "x.pdf")


# -- pdf_to_docx (best effort) ------------------------------------------

def test_pdf_to_docx_produces_valid_docx(tmp_path):
    out = convert.pdf_to_docx(_fixture("cjk.pdf"), tmp_path / "out.docx")
    assert out.exists() and out.stat().st_size > 0

    # A .docx is a zip; confirm it opens as one and python-docx can read it.
    import zipfile
    assert zipfile.is_zipfile(out)
    from docx import Document
    Document(str(out))  # must not raise


def test_pdf_to_docx_encrypted_raises(tmp_path):
    with pytest.raises(ValueError):
        convert.pdf_to_docx(_fixture("encrypted.pdf"), tmp_path / "x.docx")

"""Tests for papyrik.core.operations.enhance against the fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import pymupdf
from pypdf import PdfReader

from papyrik.core.operations import enhance
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


def _page_count(path) -> int:
    return len(PdfReader(str(path)).pages)


# -- compress ------------------------------------------------------------

def test_compress_shrinks_image_pdf(tmp_path):
    src = _fixture("scanned.pdf")
    out = enhance.compress(src, tmp_path / "c.pdf", preset="low")
    assert _page_count(out) == _page_count(src)
    assert out.stat().st_size < src.stat().st_size


def test_compress_preserves_pages_all_presets(tmp_path):
    src = _fixture("cjk.pdf")
    for preset in ("high", "balanced", "low"):
        out = enhance.compress(src, tmp_path / f"{preset}.pdf", preset=preset)
        assert _page_count(out) == 1


def test_compress_bad_preset(tmp_path):
    with pytest.raises(ValueError):
        enhance.compress(_fixture("cjk.pdf"), tmp_path / "x.pdf", preset="tiny")


def test_compress_encrypted_raises(tmp_path):
    with pytest.raises(ValueError):
        enhance.compress(_fixture("encrypted.pdf"), tmp_path / "x.pdf")


# -- watermark -----------------------------------------------------------

def test_watermark_text_adds_content(tmp_path):
    src = _fixture("cjk.pdf")
    out = enhance.watermark(src, tmp_path / "w.pdf", text="CONFIDENTIAL",
                            opacity=0.3, rotation=45, position="center")
    # The watermark text is now extractable from the output.
    with pymupdf.open(str(out)) as doc:
        assert "CONFIDENTIAL" in doc[0].get_text()
    assert _page_count(out) == 1


def test_watermark_image_runs(tmp_path):
    # Use the scanned page's embedded look: render cjk to a PNG watermark.
    from papyrik.core.operations import convert
    png = convert.pdf_to_images(_fixture("cjk.pdf"), tmp_path, fmt="png")[0]
    out = enhance.watermark(_fixture("large_300p.pdf"), tmp_path / "wi.pdf",
                            image=png, opacity=0.2, rotation=30,
                            position="bottom-right")
    assert _page_count(out) == 300


def test_watermark_text_custom_fontsize(tmp_path):
    out = enhance.watermark(_fixture("cjk.pdf"), tmp_path / "w.pdf",
                            text="BIG", fontsize=120, position="center")
    with pymupdf.open(str(out)) as doc:
        assert "BIG" in doc[0].get_text()


def test_watermark_image_custom_scale(tmp_path):
    from papyrik.core.operations import convert
    png = convert.pdf_to_images(_fixture("cjk.pdf"), tmp_path, fmt="png")[0]
    out = enhance.watermark(_fixture("cjk.pdf"), tmp_path / "wi.pdf",
                            image=png, scale=0.75, position="center")
    assert _page_count(out) == 1


def test_watermark_bad_fontsize(tmp_path):
    with pytest.raises(ValueError):
        enhance.watermark(_fixture("cjk.pdf"), tmp_path / "x.pdf",
                          text="a", fontsize=0)


def test_watermark_bad_scale(tmp_path):
    with pytest.raises(ValueError):
        enhance.watermark(_fixture("cjk.pdf"), tmp_path / "x.pdf",
                          text="a", scale=1.5)


def test_watermark_requires_exactly_one_source(tmp_path):
    with pytest.raises(ValueError):
        enhance.watermark(_fixture("cjk.pdf"), tmp_path / "x.pdf")  # neither
    with pytest.raises(ValueError):
        enhance.watermark(_fixture("cjk.pdf"), tmp_path / "x.pdf",
                          text="a", image="b.png")  # both


def test_watermark_bad_opacity(tmp_path):
    with pytest.raises(ValueError):
        enhance.watermark(_fixture("cjk.pdf"), tmp_path / "x.pdf",
                          text="a", opacity=2.0)


def test_watermark_bad_position(tmp_path):
    with pytest.raises(ValueError):
        enhance.watermark(_fixture("cjk.pdf"), tmp_path / "x.pdf",
                          text="a", position="middle")


# -- page numbers --------------------------------------------------------

def test_page_numbers_stamped(tmp_path):
    out = enhance.page_numbers(_fixture("large_300p.pdf"), tmp_path / "n.pdf",
                               start=1, position="bottom-center")
    with pymupdf.open(str(out)) as doc:
        # Page 5 should contain the stamped "5" somewhere in its text.
        assert "5" in doc[4].get_text()
    assert _page_count(out) == 300


def test_page_numbers_custom_start(tmp_path):
    out = enhance.page_numbers(_fixture("cjk.pdf"), tmp_path / "n.pdf",
                               start=100)
    with pymupdf.open(str(out)) as doc:
        assert "100" in doc[0].get_text()


def test_page_numbers_bad_position(tmp_path):
    with pytest.raises(ValueError):
        enhance.page_numbers(_fixture("cjk.pdf"), tmp_path / "x.pdf",
                             position="somewhere")

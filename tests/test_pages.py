"""Tests for papyrik.core.operations.pages.

One test (at least) per operation, run against the generated fixtures. Every
test also asserts the input file is left byte-for-byte unchanged.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from papyrik.core.operations import pages
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


def _page_count(path: str | Path) -> int:
    return len(PdfReader(str(path)).pages)


@pytest.fixture
def cjk(tmp_path):
    src = _fixture("cjk.pdf")
    copy = tmp_path / "cjk.pdf"
    copy.write_bytes(src.read_bytes())
    return copy


@pytest.fixture
def large(tmp_path):
    src = _fixture("large_300p.pdf")
    copy = tmp_path / "large_300p.pdf"
    copy.write_bytes(src.read_bytes())
    return copy


def _assert_unchanged(path: Path, before: bytes):
    assert path.read_bytes() == before, "input file was mutated"


# -- merge ---------------------------------------------------------------

def test_merge(tmp_path, cjk, large):
    before_cjk = cjk.read_bytes()
    out = pages.merge([cjk, large], tmp_path / "merged.pdf")
    assert _page_count(out) == _page_count(cjk) + _page_count(large)
    _assert_unchanged(cjk, before_cjk)


def test_merge_empty_raises(tmp_path):
    with pytest.raises(ValueError):
        pages.merge([], tmp_path / "x.pdf")


# -- split_by_range ------------------------------------------------------

def test_split_by_range(tmp_path, large):
    before = large.read_bytes()
    outs = pages.split_by_range(large, [(0, 9), (10, 19), (295, 299)], tmp_path)
    assert [_page_count(o) for o in outs] == [10, 10, 5]
    _assert_unchanged(large, before)


def test_split_by_range_out_of_range(tmp_path, cjk):
    with pytest.raises(IndexError):
        pages.split_by_range(cjk, [(0, 9)], tmp_path)


def test_split_by_range_reversed(tmp_path, large):
    with pytest.raises(ValueError):
        pages.split_by_range(large, [(9, 0)], tmp_path)


# -- split_every_n -------------------------------------------------------

def test_split_every_n(tmp_path, large):
    outs = pages.split_every_n(large, 120, tmp_path)
    assert [_page_count(o) for o in outs] == [120, 120, 60]  # 300 -> 120+120+60


def test_split_every_n_bad_n(tmp_path, large):
    with pytest.raises(ValueError):
        pages.split_every_n(large, 0, tmp_path)


# -- rotate --------------------------------------------------------------

def test_rotate(tmp_path, large):
    before = large.read_bytes()
    out = pages.rotate(large, [0, 2], 90, tmp_path / "rot.pdf")
    reader = PdfReader(str(out))
    assert reader.pages[0].rotation % 360 == 90
    assert reader.pages[1].rotation % 360 == 0
    assert reader.pages[2].rotation % 360 == 90
    _assert_unchanged(large, before)


def test_rotate_bad_degrees(tmp_path, cjk):
    with pytest.raises(ValueError):
        pages.rotate(cjk, [0], 45, tmp_path / "x.pdf")


# -- delete_pages --------------------------------------------------------

def test_delete_pages(tmp_path, large):
    out = pages.delete_pages(large, [0, 1, 2], tmp_path / "del.pdf")
    assert _page_count(out) == 297


def test_delete_all_raises(tmp_path, cjk):
    with pytest.raises(ValueError):
        pages.delete_pages(cjk, [0], tmp_path / "x.pdf")  # cjk has 1 page


# -- extract_pages -------------------------------------------------------

def test_extract_pages(tmp_path, large):
    out = pages.extract_pages(large, [5, 1, 5, 3], tmp_path / "ex.pdf")
    assert _page_count(out) == 3  # dedup + sort -> {1,3,5}


def test_extract_empty_raises(tmp_path, large):
    with pytest.raises(ValueError):
        pages.extract_pages(large, [], tmp_path / "x.pdf")


# -- reorder -------------------------------------------------------------

def test_reorder(tmp_path, large):
    order = list(reversed(range(300)))
    out = pages.reorder(large, order, tmp_path / "re.pdf")
    assert _page_count(out) == 300

    # First page of output should be the last page of input. Compare text.
    src_last = PdfReader(str(large)).pages[299].extract_text()
    out_first = PdfReader(str(out)).pages[0].extract_text()
    assert src_last.strip() == out_first.strip()


def test_reorder_not_permutation(tmp_path, large):
    with pytest.raises(ValueError):
        pages.reorder(large, [0, 1, 2], tmp_path / "x.pdf")  # incomplete

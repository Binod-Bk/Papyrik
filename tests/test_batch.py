"""Tests for papyrik.core.batch."""

from __future__ import annotations

import shutil
from pathlib import Path

from papyrik.core import batch
from papyrik.core.operations import enhance
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


def _seed_folder(dst: Path, names: list[str]) -> Path:
    dst.mkdir(parents=True, exist_ok=True)
    for name in names:
        shutil.copyfile(_fixture(name), dst / name)
    return dst


_COMPRESS = staticmethod(lambda s, d: enhance.compress(s, d, "high"))


def test_batch_processes_every_pdf(tmp_path):
    src = _seed_folder(tmp_path / "in", ["cjk.pdf", "form.pdf"])
    out = tmp_path / "out"
    results = batch.run_batch(src, lambda s, d: enhance.compress(s, d, "high"),
                              out, suffix="_c")
    assert len(results) == 2
    assert all(err is None for _in, _out, err in results)
    assert (out / "cjk_c.pdf").exists()
    assert (out / "form_c.pdf").exists()


def test_batch_records_per_file_errors(tmp_path):
    src = _seed_folder(tmp_path / "in", ["cjk.pdf", "corrupt.pdf"])
    out = tmp_path / "out"
    results = batch.run_batch(src, lambda s, d: enhance.compress(s, d, "high"),
                              out)
    by_name = {p.name: (o, e) for p, o, e in results}
    assert by_name["cjk.pdf"][1] is None          # succeeded
    assert by_name["corrupt.pdf"][0] is None       # no output
    assert by_name["corrupt.pdf"][1] is not None    # has an error message


def test_batch_reports_progress(tmp_path):
    src = _seed_folder(tmp_path / "in", ["cjk.pdf", "form.pdf"])
    ticks: list[tuple[int, int]] = []
    batch.run_batch(src, lambda s, d: enhance.compress(s, d, "high"),
                    tmp_path / "out", progress=lambda d, t: ticks.append((d, t)))
    assert ticks == [(1, 2), (2, 2)]


def test_batch_empty_folder(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    results = batch.run_batch(src, lambda s, d: None, tmp_path / "out")
    assert results == []


def test_batch_guards_overwrite(tmp_path):
    src = _seed_folder(tmp_path / "in", ["cjk.pdf"])
    # Same dir, no suffix -> output path equals input -> guarded, not clobbered.
    results = batch.run_batch(src, lambda s, d: enhance.compress(s, d, "high"),
                              src)
    _in, out, err = results[0]
    assert out is None and "overwrite" in err

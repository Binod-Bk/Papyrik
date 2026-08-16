"""Tests for papyrik.core.operations.security against the fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf import PdfReader

from papyrik.core.document import is_encrypted
from papyrik.core.operations import security
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES
PASSWORD = make_fixtures.ENCRYPTED_PASSWORD


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


# -- encrypt -------------------------------------------------------------

def test_encrypt_produces_protected_file(tmp_path):
    out = security.encrypt(_fixture("cjk.pdf"), "hunter2", tmp_path / "enc.pdf")
    assert is_encrypted(out) is True

    reader = PdfReader(str(out))
    assert reader.is_encrypted
    assert reader.decrypt("hunter2") != 0          # correct password opens
    assert len(reader.pages) == 1


def test_encrypt_wrong_password_fails_to_open(tmp_path):
    out = security.encrypt(_fixture("cjk.pdf"), "hunter2", tmp_path / "enc.pdf")
    reader = PdfReader(str(out))
    assert reader.decrypt("nope") == 0


def test_encrypt_empty_password_raises(tmp_path):
    with pytest.raises(ValueError):
        security.encrypt(_fixture("cjk.pdf"), "", tmp_path / "x.pdf")


def test_encrypt_already_encrypted_raises(tmp_path):
    with pytest.raises(ValueError):
        security.encrypt(_fixture("encrypted.pdf"), "pw", tmp_path / "x.pdf")


def test_input_not_modified(tmp_path):
    src = _fixture("cjk.pdf")
    before = src.read_bytes()
    security.encrypt(src, "pw", tmp_path / "enc.pdf")
    assert src.read_bytes() == before


# -- decrypt -------------------------------------------------------------

def test_decrypt_removes_password(tmp_path):
    out = security.decrypt(_fixture("encrypted.pdf"), PASSWORD, tmp_path / "dec.pdf")
    assert is_encrypted(out) is False
    assert len(PdfReader(str(out)).pages) == 1


def test_decrypt_wrong_password_raises(tmp_path):
    with pytest.raises(ValueError):
        security.decrypt(_fixture("encrypted.pdf"), "nope", tmp_path / "x.pdf")


def test_decrypt_plain_file_raises(tmp_path):
    with pytest.raises(ValueError):
        security.decrypt(_fixture("cjk.pdf"), "pw", tmp_path / "x.pdf")


# -- roundtrip -----------------------------------------------------------

def test_encrypt_then_decrypt_roundtrip(tmp_path):
    enc = security.encrypt(_fixture("large_300p.pdf"), "pw", tmp_path / "e.pdf")
    dec = security.decrypt(enc, "pw", tmp_path / "d.pdf")
    assert is_encrypted(dec) is False
    assert len(PdfReader(str(dec)).pages) == 300

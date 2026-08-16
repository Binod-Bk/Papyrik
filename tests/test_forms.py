"""Tests for papyrik.core.operations.forms against the form fixture."""

from __future__ import annotations

from pathlib import Path

import pytest

from papyrik.core.operations import forms
from tests import make_fixtures

FIXTURES = make_fixtures.FIXTURES


def _fixture(name: str) -> Path:
    path = FIXTURES / name
    if not path.exists():
        make_fixtures.main()
    return path


def _by_name(fields: list[dict]) -> dict[str, dict]:
    return {f["name"]: f for f in fields}


# -- read ----------------------------------------------------------------

def test_read_fields_lists_form_fields():
    fields = _by_name(forms.read_fields(_fixture("form.pdf")))
    assert "full_name" in fields
    assert fields["full_name"]["type"] == "Text"
    assert "subscribe" in fields
    assert fields["subscribe"]["type"] == "CheckBox"
    assert "Off" in fields["subscribe"]["options"]


def test_read_fields_empty_for_plain_pdf():
    assert forms.read_fields(_fixture("cjk.pdf")) == []


def test_read_encrypted_raises():
    with pytest.raises(ValueError):
        forms.read_fields(_fixture("encrypted.pdf"))


# -- fill ----------------------------------------------------------------

def test_fill_text_field(tmp_path):
    out = forms.fill_fields(_fixture("form.pdf"),
                            {"full_name": "Binod B K"}, tmp_path / "f.pdf")
    fields = _by_name(forms.read_fields(out))
    assert fields["full_name"]["value"] == "Binod B K"


def test_fill_checkbox(tmp_path):
    on = _by_name(forms.read_fields(_fixture("form.pdf")))["subscribe"]["options"][0]
    out = forms.fill_fields(_fixture("form.pdf"),
                            {"subscribe": on}, tmp_path / "f.pdf")
    assert _by_name(forms.read_fields(out))["subscribe"]["value"] == on


def test_fill_does_not_modify_input(tmp_path):
    src = _fixture("form.pdf")
    before = src.read_bytes()
    forms.fill_fields(src, {"full_name": "X"}, tmp_path / "f.pdf")
    assert src.read_bytes() == before


def test_fill_unknown_field_is_noop(tmp_path):
    out = forms.fill_fields(_fixture("form.pdf"),
                            {"nonexistent": "x"}, tmp_path / "f.pdf")
    assert _by_name(forms.read_fields(out))["full_name"]["value"] == ""

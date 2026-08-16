"""Forms: read and fill existing AcroForm fields (no form creation).

Pure functions - the input file is never modified. `read_fields` reports each
fillable field's name, type, current value and (for choices/checkboxes) its
options; `fill_fields` writes new values to a copy.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf

# Widget types Papyrik can fill. Pushbuttons and signatures are ignored.
_FILLABLE = {"Text", "CheckBox", "ComboBox", "ListBox", "RadioButton"}


def _open_pdf(path: str | Path) -> pymupdf.Document:
    doc = pymupdf.open(str(path))
    if doc.needs_pass:
        doc.close()
        raise ValueError(
            f"'{Path(path).name}' is password-protected; decrypt it first."
        )
    return doc


def _checkbox_on(widget: pymupdf.Widget) -> str:
    try:
        return widget.on_state() or "Yes"
    except Exception:
        return "Yes"


def read_fields(input_pdf: str | Path) -> list[dict]:
    """Return the fillable form fields as dicts.

    Each dict: {"name", "type", "value", "options"}. `options` is the choice
    list for ComboBox/ListBox or [on, "Off"] for CheckBox/RadioButton, else [].
    """
    doc = _open_pdf(input_pdf)
    try:
        fields: list[dict] = []
        seen: set[str] = set()
        for page in doc:
            for widget in page.widgets() or ():
                name = widget.field_name
                ftype = widget.field_type_string
                if not name or name in seen or ftype not in _FILLABLE:
                    continue
                seen.add(name)
                info = {"name": name, "type": ftype,
                        "value": "", "options": []}
                raw = widget.field_value
                if ftype in ("ComboBox", "ListBox"):
                    info["options"] = list(widget.choice_values or [])
                    info["value"] = raw if isinstance(raw, str) else ""
                elif ftype in ("CheckBox", "RadioButton"):
                    on = _checkbox_on(widget)
                    info["options"] = [on, "Off"]
                    checked = raw not in (False, "Off", "", None)
                    info["value"] = on if checked else "Off"
                else:  # Text
                    info["value"] = raw if isinstance(raw, str) else ""
                fields.append(info)
        return fields
    finally:
        doc.close()


def fill_fields(input_pdf: str | Path, values: dict[str, str],
                output: str | Path) -> Path:
    """Write a copy of `input_pdf` with the named fields set to `values`."""
    doc = _open_pdf(input_pdf)
    try:
        for page in doc:
            for widget in page.widgets() or ():
                name = widget.field_name
                if name in values:
                    widget.field_value = values[name]
                    widget.update()
        out = Path(output)
        out.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(out), garbage=3, deflate=True)
        return out
    finally:
        doc.close()

"""Form-fill dialog - one input per existing AcroForm field."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class FormDialog(QDialog):
    def __init__(self, fields: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Fill Form")
        self.setMinimumWidth(460)

        self._fields = fields
        self._widgets: dict[str, QWidget] = {}

        form_host = QWidget()
        form = QFormLayout(form_host)
        for field in fields:
            form.addRow(field["name"] + ":", self._make_widget(field))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_host)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)
        self.resize(500, min(120 + 40 * len(fields), 720))

    def _make_widget(self, field: dict) -> QWidget:
        ftype, value, options = field["type"], field["value"], field["options"]
        if ftype in ("CheckBox", "RadioButton"):
            box = QCheckBox()
            box.setChecked(value not in ("Off", "", None))
            widget: QWidget = box
        elif ftype in ("ComboBox", "ListBox"):
            combo = QComboBox()
            combo.addItems(options)
            if value:
                combo.setCurrentText(value)
            widget = combo
        else:  # Text
            widget = QLineEdit(value or "")
        self._widgets[field["name"]] = widget
        return widget

    def values(self) -> dict[str, str]:
        result: dict[str, str] = {}
        for field in self._fields:
            name, ftype = field["name"], field["type"]
            widget = self._widgets[name]
            if ftype in ("CheckBox", "RadioButton"):
                on = field["options"][0] if field["options"] else "Yes"
                result[name] = on if widget.isChecked() else "Off"
            elif ftype in ("ComboBox", "ListBox"):
                result[name] = widget.currentText()
            else:
                result[name] = widget.text()
        return result

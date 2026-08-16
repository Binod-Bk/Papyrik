"""Metadata view/edit dialog - a form over the editable Info fields."""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QWidget,
)

from papyrik.core.operations.metadata import FIELDS


class MetadataDialog(QDialog):
    def __init__(self, values: dict[str, str],
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Document Metadata")
        self.setMinimumWidth(420)

        self._edits: dict[str, QLineEdit] = {}
        form = QFormLayout(self)
        for field in FIELDS:
            edit = QLineEdit(values.get(field, ""))
            self._edits[field] = edit
            form.addRow(field.capitalize() + ":", edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def values(self) -> dict[str, str]:
        return {field: edit.text() for field, edit in self._edits.items()}

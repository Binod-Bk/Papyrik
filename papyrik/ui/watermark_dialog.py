"""Watermark options dialog - collects params for enhance.watermark."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QSpinBox,
    QWidget,
)

POSITIONS = [
    "center", "top", "bottom", "left", "right",
    "top-left", "top-right", "bottom-left", "bottom-right",
]


class WatermarkDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Watermark")
        self._image_path: str = ""

        self._text_radio = QRadioButton("Text")
        self._image_radio = QRadioButton("Image")
        self._text_radio.setChecked(True)
        self._text_radio.toggled.connect(self._sync_enabled)

        mode = QHBoxLayout()
        mode.addWidget(self._text_radio)
        mode.addWidget(self._image_radio)
        mode.addStretch(1)

        self._text = QLineEdit("CONFIDENTIAL")

        self._image_label = QLabel("No image selected")
        self._image_label.setStyleSheet("color: palette(mid);")
        browse = QPushButton("Choose…")
        browse.clicked.connect(self._choose_image)
        image_row = QHBoxLayout()
        image_row.addWidget(self._image_label, 1)
        image_row.addWidget(browse)

        self._opacity = QSlider(Qt.Orientation.Horizontal)
        self._opacity.setRange(5, 100)
        self._opacity.setValue(30)
        self._opacity_label = QLabel("30%")
        self._opacity.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self._opacity, 1)
        opacity_row.addWidget(self._opacity_label)

        self._rotation = QSpinBox()
        self._rotation.setRange(-180, 180)
        self._rotation.setValue(45)
        self._rotation.setSuffix("°")

        self._position = QComboBox()
        self._position.addItems(POSITIONS)

        form = QFormLayout()
        form.addRow(mode)
        form.addRow("Text:", self._text)
        form.addRow("Image:", self._wrap(image_row))
        form.addRow("Opacity:", self._wrap(opacity_row))
        form.addRow("Rotation:", self._rotation)
        form.addRow("Position:", self._position)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

        self.setLayout(form)
        self._sync_enabled()

    @staticmethod
    def _wrap(layout) -> QWidget:
        w = QWidget()
        w.setLayout(layout)
        return w

    def _sync_enabled(self) -> None:
        text_mode = self._text_radio.isChecked()
        self._text.setEnabled(text_mode)

    def _choose_image(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose watermark image", "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if path:
            self._image_path = path
            self._image_label.setText(path.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
            self._image_radio.setChecked(True)

    def _on_accept(self) -> None:
        if self._text_radio.isChecked() and not self._text.text().strip():
            self._text.setFocus()
            return
        if self._image_radio.isChecked() and not self._image_path:
            self._choose_image()
            if not self._image_path:
                return
        self.accept()

    def params(self) -> dict:
        """Keyword args for enhance.watermark based on the chosen options."""
        common = {
            "opacity": self._opacity.value() / 100.0,
            "rotation": self._rotation.value(),
            "position": self._position.currentText(),
        }
        if self._text_radio.isChecked():
            return {"text": self._text.text(), **common}
        return {"image": self._image_path, **common}

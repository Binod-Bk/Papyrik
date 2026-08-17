"""Papyrik entry point.

Opens the main window with the branded theme and app icon. The window shell
(sidebar tool list, central preview, right-hand tool panel) is assembled in
`ui.main_window`.
"""

from __future__ import annotations

import sys

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from papyrik import APP_NAME
from papyrik.resources import resource_path
from papyrik.ui.main_window import MainWindow
from papyrik.ui.theme import apply_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    icon_path = resource_path("papyrik.ico")
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))

    apply_theme(app)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

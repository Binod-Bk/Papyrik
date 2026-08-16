"""Papyrik entry point.

Opens the main window. No PDF operations are wired here — the window shell
(sidebar tool list, central preview, right-hand tool panel) is assembled in
`ui.main_window`.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from papyrik import APP_NAME
from papyrik.ui.main_window import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_NAME)

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

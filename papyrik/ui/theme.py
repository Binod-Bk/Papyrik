"""Papyrik visual theme - a cohesive dark palette applied app-wide as a stylesheet.

Brand: indigo accent (#7C6BF0), warm paper text, amber highlight - matching the
logo. Applied once in main() via apply_theme(app).
"""

from __future__ import annotations

from PyQt6.QtWidgets import QApplication

# Palette - near-black base with an electric-blue accent; amber stays as the
# secondary highlight to tie back to the logo.
BG_0 = "#0A0A0D"       # window background (near-black)
BG_1 = "#121319"       # panels / sidebar
BG_2 = "#1B1D26"       # inputs / hover
BG_3 = "#242731"       # pressed / selection base
BORDER = "#262A35"
TEXT = "#EAECF3"
MUTED = "#888FA1"
ACCENT = "#2563EB"     # electric blue
ACCENT_HOVER = "#3B7BF5"
ACCENT_PRESSED = "#1D4FC7"
AMBER = "#FFC24B"

_QSS = f"""
* {{
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    color: {TEXT};
}}
QMainWindow, QDialog, QWidget {{
    background: {BG_0};
}}

/* Sidebar + page grid share QListWidget */
QListWidget {{
    background: {BG_1};
    border: none;
    outline: 0;
    padding: 6px;
}}
QListWidget::item {{
    padding: 8px 12px;
    margin: 1px 4px;
    border-radius: 8px;
    color: {TEXT};
}}
QListWidget::item:hover {{
    background: {BG_2};
}}
QListWidget::item:selected {{
    background: {ACCENT};
    color: white;
}}
QListWidget::item:disabled {{            /* sidebar group headers */
    color: {MUTED};
    font-size: 11px;
    font-weight: 700;
    padding: 12px 12px 4px 12px;
    margin: 0;
    background: transparent;
}}

/* Central page grid: give thumbnails room, subtle selection */
QListWidget#pageGrid {{
    background: {BG_0};
    padding: 10px;
}}
QListWidget#pageGrid::item {{
    color: {MUTED};
    margin: 6px;
    border-radius: 10px;
}}
QListWidget#pageGrid::item:selected {{
    background: {BG_3};
    color: {TEXT};
    border: 1px solid {ACCENT};
}}

/* Menu bar */
QMenuBar {{ background: {BG_1}; padding: 2px 6px; }}
QMenuBar::item {{ padding: 6px 10px; border-radius: 6px; background: transparent; }}
QMenuBar::item:selected {{ background: {BG_2}; }}
QMenu {{ background: {BG_1}; border: 1px solid {BORDER}; border-radius: 8px; padding: 4px; }}
QMenu::item {{ padding: 7px 22px; border-radius: 6px; }}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 4px 8px; }}

/* Buttons */
QPushButton {{
    background: {BG_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 7px 14px;
    color: {TEXT};
}}
QPushButton:hover {{ background: {BG_3}; }}
QPushButton:pressed {{ background: {BG_1}; }}
QPushButton:disabled {{ color: {MUTED}; background: {BG_1}; }}
QPushButton:default, QPushButton#primary {{
    background: {ACCENT};
    border: 1px solid {ACCENT};
    color: white;
    font-weight: 600;
}}
QPushButton:default:hover, QPushButton#primary:hover {{ background: {ACCENT_HOVER}; }}
QPushButton:default:pressed, QPushButton#primary:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton:checked {{ background: {ACCENT}; border-color: {ACCENT}; color: white; }}

/* Inputs */
QLineEdit, QComboBox, QSpinBox, QTextEdit, QPlainTextEdit {{
    background: {BG_2};
    border: 1px solid {BORDER};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {ACCENT};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox QAbstractItemView {{
    background: {BG_1};
    border: 1px solid {BORDER};
    border-radius: 8px;
    selection-background-color: {ACCENT};
    outline: 0;
}}

/* Checkbox */
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 18px; height: 18px;
    border: 1px solid {BORDER};
    border-radius: 5px;
    background: {BG_2};
}}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

/* Progress */
QProgressBar {{
    background: {BG_2};
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 6px; }}

/* Scrollbars */
QScrollBar:vertical {{ background: transparent; width: 12px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {BG_3}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {ACCENT}; }}
QScrollBar:horizontal {{ background: transparent; height: 12px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {BG_3}; border-radius: 5px; min-width: 30px; }}
QScrollBar::handle:horizontal:hover {{ background: {ACCENT}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

/* Splitter + status bar */
QSplitter::handle {{ background: {BORDER}; }}
QSplitter::handle:hover {{ background: {ACCENT}; }}
QStatusBar {{ background: {BG_1}; color: {MUTED}; border-top: 1px solid {BORDER}; }}
QToolTip {{
    background: {BG_1}; color: {TEXT};
    border: 1px solid {BORDER}; border-radius: 6px; padding: 5px 8px;
}}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyleSheet(_QSS)

#!/usr/bin/env python3
"""Stock Ranger — entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication

from stock_ranger.ui.main_window import MainWindow

_ICON = Path(__file__).resolve().parent / "assets" / "stock-ranger.svg"


def main() -> int:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("Stock Ranger")
    app.setApplicationDisplayName("Stock Ranger")
    # Asosiasi ke .desktop (penting di Wayland agar icon launcher cocok).
    app.setDesktopFileName("stock-ranger")
    if _ICON.exists():
        app.setWindowIcon(QIcon(str(_ICON)))

    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())

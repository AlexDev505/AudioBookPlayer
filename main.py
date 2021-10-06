from __future__ import annotations

import sys

from PyQt5.QtWidgets import QApplication

import config  # Noqa
from start_app import StartAppWindow
from main_window import MainWindow

app = QApplication([])
window = StartAppWindow()
window.installEventFilter(window)
window.show()
sys.exit(app.exec())

from __future__ import annotations

import config  # noqa
import os
import sys
import time
import typing as ty

from PyQt5 import QtWidgets, QtGui, QtCore

from ui import UiMainWindow
from database import Books


class Window(QtWidgets.QMainWindow, UiMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.setupUi(self)

        # self.setup_signals()
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.closeAppBtn.clicked.connect(self.close)

        # CUSTOM GRIPS
        # self.left_grip = QtCore.CustomGrip(self, Qt.LeftEdge, True)
        # self.right_grip = CustomGrip(self, Qt.RightEdge, True)
        # self.top_grip = CustomGrip(self, Qt.TopEdge, True)
        # self.bottom_grip = CustomGrip(self, Qt.BottomEdge, True)


app = QtWidgets.QApplication([])
application = Window()
application.show()

sys.exit(app.exec())

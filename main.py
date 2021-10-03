from __future__ import annotations

import config  # noqa
import os
import sys
import time
import typing as ty
from ui_functions import (
    control_panel,
    library,
    menu,
    sliders,
    window_geometry,
)

from PyQt5 import QtWidgets, QtGui, QtCore

from ui import UiMainWindow
from database import Books

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QObject, QEvent


class Window(QtWidgets.QMainWindow, UiMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.setupUi(self)

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setupSignals()

    def setupSignals(self):
        # APPLICATION
        self.closeAppBtn.clicked.connect(self.close)
        self.fullscreenAppBtn.clicked.connect(
            lambda: window_geometry.toggleFullScreen(self)
        )
        self.minimizeAppBtn.clicked.connect(self.showMinimized)

        self.logo.mousePressEvent = lambda e: window_geometry.dragZonePressEvent(
            self, e
        )
        self.logo.mouseMoveEvent = lambda e: window_geometry.dragZoneMoveEvent(self, e)
        self.logo.mouseReleaseEvent = lambda e: window_geometry.dragZoneReleaseEvent(
            self, e
        )

        # MENU
        self.menuBtn.clicked.connect(lambda e: menu.toggleMenu(self))
        self.menuButtons.buttonClicked.connect(
            lambda btn: menu.buttonsHandler(self, btn)
        )

        # LIBRARY
        self.toggleBooksFilterPanelBtn.clicked.connect(
            lambda *e: library.toggleFiltersPanel(self)
        )

        # CONTROL PANEL
        self.controlPanelButtons.buttonClicked.connect(
            lambda btn: control_panel.buttonsHandler(self, btn)
        )

        self.volumeSlider.valueChanged.connect(
            lambda value: control_panel.volumeSliderHandler(self, value)
        )
        oldVolumeSliderMousePressEvent = self.volumeSlider.mousePressEvent
        self.volumeSlider.mousePressEvent = lambda e: sliders.mousePressEvent(
            e, self.volumeSlider, oldVolumeSliderMousePressEvent
        )

        self.speedSlider.valueChanged.connect(
            lambda value: control_panel.speedSliderHandler(self, value)
        )
        oldSpeedSliderMousePressEvent = self.speedSlider.mousePressEvent
        self.speedSlider.mousePressEvent = lambda e: sliders.mousePressEvent(
            e, self.speedSlider, oldSpeedSliderMousePressEvent
        )

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        window_geometry.mouseEvent(self, event)

        return super(Window, self).eventFilter(obj, event)


app = QtWidgets.QApplication([])
window = Window()
window.installEventFilter(window)
window.show()

sys.exit(app.exec())

from __future__ import annotations

import config  # noqa
import os
import sys
import time
import typing as ty
from ui_functions import window_geometry

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
        self.closeAppBtn.clicked.connect(self.close)
        self.fullscreenAppBtn.clicked.connect(
            lambda: window_geometry.toggleFullScreen(self)
        )
        self.minimizeAppBtn.clicked.connect(self.showMinimized)

        self.logo.mousePressEvent = lambda e: window_geometry.mousePressEvent(self, e)
        self.logo.mouseMoveEvent = lambda e: window_geometry.mouseMoveEvent(self, e)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        window_geometry.mouseEvent(self, event)

        return super(Window, self).eventFilter(obj, event)


app = QtWidgets.QApplication([])
window = Window()
# window.setStyleSheet(
#     """QWidget {
#     color: rgb(142, 146, 151);
# }
# /* QFrame */
# QFrame {
#     border: none;
# }
# /*  BUTTONS */
# QPushButton {
#     background-color: rgba(0, 0, 0, 0);
#     border-radius: 5px;
#     border: none;
# }
# QPushButton:hover {
#     background-color: #34373C;
#     border-radius: 5px;
# }
# QPushButton:pressed {
#     background-color: #37393F;
# }
# /* LINE EDIT */
# QLineEdit {
#     background-color: rgb(64, 68, 75);
#     border-radius: 5px;
#     padding-left:3px;
#     border: none;
# }
# /* COMBOBOX */
# QComboBox {
#     background-color: rgb(64, 68, 75);
#     border-radius: 5px;
#     border: none;
# }
# QComboBox QAbstractItemView {
#       selection-background-color:  rgb(50, 53, 59);
# }
# QComboBox::drop-down {
#     border: none;
# }
# QComboBox::down-arrow {
#     image: url(:/other/angle_down.svg);
#     border: none;
#     width: 35px;
#     height: 35px;
#     padding-right: 20px;
# }
# /*  TOOLTIP */
# QToolTip {
#     border: none;
#     background-color: rgb(29, 30, 34);
#     border-left: 2px solid rgb(142, 146, 151);
#     color: rgb(142, 146, 151);
#     text-align: left;
#     padding: 4px;
# }
# /* SLIDER */
# QSlider {
#     background-color: rgb(41, 43, 47);
# }
# QSlider::groove:horizontal {
#     background: rgb(64, 68, 75);
#     border-radius: 1px;
# }
# QSlider::sub-page:horizontal {
#     background: rgb(142, 146, 151);
#     border-radius: 1px;
#     height: 40px;
# }
# QSlider::add-page:horizontal {
#     background: rgb(64, 68, 75);
#     border-radius: 1px;
#     height: 40px;
# }
# QSlider::handle:horizontal {
#     background: rgb(142, 146, 151);
#     border: 0px;
#     width: 8px;
#     margin-top: 0px;
#     margin-bottom: 0px;
#     border-radius: 1px;
# }
# /* TAB WIDGET */
# QTabWidget::pane {
#     border: none;
# }
# QTabBar::tab {
#     background: rgba(0, 0, 0, 0);
#     padding: 10px;
#     font-weight: normal;
#      border: none;
# }
# QTabBar::tab:selected {
#       background: rgba(0, 0, 0, 0);
#     border-top: 2px solid #fff;
#     font-weight: bold;
#     margin-bottom: -1px;
# }
# /*SCROLLBAR */
# QScrollArea {
#     border: none;
# }
# /* VERTICAL SCROLLBAR */
#  QScrollBar:vertical {
#     border: none;
#     width: 8px;
#     margin: 15px 0px 15px 0 px;
#  }
# /*  HANDLE BAR VERTICAL */
# QScrollBar::handle:vertical {
#     background-color: rgb(32, 34, 37);
#     min-height: 30px;
#     border-radius: 4px;
# }
# /* BTN TOP - SCROLLBAR */
# QScrollBar::sub-line:vertical {
#     height: 0px;
# }
# /* BTN BOTTOM - SCROLLBAR */
# QScrollBar::add-line:vertical {
#     height: 0px;
# }
# /* RESET ARROW */
# QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
#     background: rgb(46, 51, 56);
#     border-radius: 4px;
# }
# QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
#     background: rgb(46, 51, 56);
#     border-radius: 4px;
# }
# /**/
# Line {
#     background-color: rgb(45, 47, 50);
# }
# /* TOP FRAME */
# #topFrame {
#     background-color: rgb(32, 34, 37);
# }
# /*  MENU */
# #menuFrame {
#     background-color: rgb(32, 34, 37);
# }
# #menuFrame * {
#     text-align: left;
# }
# #menuFrame QPushButton {
#     padding: 6px 10px 6px 10px;
# }
# /*  CONTENT */
# #content, #stackedWidget, #libraryPage, #addBookPage, #searchResultPage, #settingsPage {
#     background-color: rgb(32, 34, 37);
# }
# #libraryPageContent, #addBookPageContent, #searchResultPageContent, #settingsPageContent {
#     background-color: rgb(54, 57, 63);
#     border-top-left-radius: 15px;
# }
# /* LIBRARY PAGE CONTENT */
# #libraryPageContent QTabWidget *{
#     background-color: rgb(54, 57, 63);
# }
# /* SEARCH RESULT PAGE CONTENT */
# #driversList, #driversListLayout {
#     background-color: rgb(47, 49, 54);
#     border-top-left-radius: 15px;
#     text-align: left;
# }
# /* LIBRARY FILTERS PANEL */
# #libraryFiltersPanel {
#     background-color: rgb(47, 49, 54);
#     border-top-left-radius: 15px;
# }
# #libraryFiltersPanel QFrame {
#     background-color: rgb(47, 49, 54);
# }
# #toggleBooksFilterPanelBtn {
#     background-color: rgb(54, 57, 63);
#     border-radius: 0px;
#     border-top-left-radius: 15px;
# }
# #toggleBooksFilterPanelBtn:hover {
#     background-color: rgb(50, 53, 59);
# }
# /*  CONTROL PANEL */
# #controlPanel, #controlPanel QFrame {
#     background-color: rgb(41, 43, 47);
# }"""
# )
window.installEventFilter(window)
window.show()

sys.exit(app.exec())

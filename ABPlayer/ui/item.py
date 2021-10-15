from __future__ import annotations

import typing as ty
import re

from PyQt5 import QtCore, QtGui, QtWidgets

from ui_functions import sliders

if ty.TYPE_CHECKING:
    from main import MainWindow
    from database.tables.books import BookItem


def convert_into_seconds(seconds: int) -> str:
    """
    :param seconds: Число секунд.
    :return: Строка вида `<часы>:<минуты>:<секунды>`.
    """
    h = seconds // 3600
    m = seconds % 3600 // 60
    s = seconds % 60
    return ((str(h).rjust(2, "0") + ":") if h else "") + ":".join(
        map(lambda x: str(x).rjust(2, "0"), (m, s))
    )


class UiItem(object):
    def setupUi(self, Item):
        Item.setObjectName("Item")
        Item.resize(655, 50)
        Item.setMaximumSize(QtCore.QSize(16777215, 50))
        self.horizontalLayout = QtWidgets.QHBoxLayout(Item)
        self.horizontalLayout.setContentsMargins(0, 0, 0, 0)
        self.horizontalLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("horizontalLayout")
        self.slider = QtWidgets.QSlider(Item)
        self.slider.setWindowFlag(QtCore.Qt.WindowStaysOnTopHint)
        self.slider.setMinimumSize(QtCore.QSize(0, 50))
        self.slider.setFocusPolicy(QtCore.Qt.NoFocus)
        self.slider.setOrientation(QtCore.Qt.Horizontal)
        self.slider.setObjectName("slider")
        self.horizontalLayout.addWidget(self.slider)

        font = QtGui.QFont()
        font.setFamily("Arial")
        font.setPointSize(12)
        font.setBold(True)
        font.setWeight(75)

        self.sliderLayout = QtWidgets.QHBoxLayout(self.slider)
        self.sliderLayout.setContentsMargins(15, 0, 15, 0)
        self.sliderLayout.setSpacing(0)
        self.horizontalLayout.setObjectName("sliderLayout")

        self.title = QtWidgets.QLabel(self.slider)
        self.title.setFont(font)
        self.title.setStyleSheet("background-color: rgba(0,0,0,0)")
        self.title.setText("01")
        self.title.setObjectName("title")
        self.sliderLayout.addWidget(self.title)

        spacerItem = QtWidgets.QSpacerItem(
            155, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.sliderLayout.addItem(spacerItem)

        font = QtGui.QFont()
        font.setFamily("Arial")
        font.setPointSize(10)
        font.setBold(True)
        font.setWeight(75)
        self.progressFrame = QtWidgets.QFrame(self.slider)
        self.progressFrame.setStyleSheet("background-color: rgba(0,0,0,0)")
        self.progressFrame.setObjectName("progressFrame")
        self.progressLayout = QtWidgets.QHBoxLayout(self.progressFrame)
        self.progressLayout.setContentsMargins(0, 0, 0, 0)
        self.progressLayout.setSpacing(0)
        self.progressLayout.setObjectName("progressLayout")
        self.doneTime = QtWidgets.QLabel(self.progressFrame)
        self.doneTime.setFont(font)
        self.doneTime.setText("00:00")
        self.doneTime.setObjectName("doneTime")
        self.progressLayout.addWidget(self.doneTime)
        self.separator = QtWidgets.QLabel(self.progressFrame)
        self.separator.setFont(font)
        self.separator.setText(" / ")
        self.separator.setObjectName("separator")
        self.progressLayout.addWidget(self.separator)
        self.totalTime = QtWidgets.QLabel(self.progressFrame)
        self.totalTime.setFont(font)
        self.totalTime.setText("05:00")
        self.totalTime.setObjectName("totalTime")
        self.progressLayout.addWidget(self.totalTime)
        self.sliderLayout.addWidget(self.progressFrame)

        QtCore.QMetaObject.connectSlotsByName(Item)


class Item(QtWidgets.QFrame, UiItem):
    def __init__(
        self,
        main_window: MainWindow,
        parent: QtWidgets.QWidget,
        item: BookItem,
        done_time: int = None,
    ):
        super(Item, self).__init__(parent)
        self.setupUi(self)
        parent.layout().addWidget(self)

        sliders.prepareSlider(self.slider)
        self.slider.wheelEvent = lambda e: None

        self.title.setText(item.title)
        self.totalTime.setText(
            f"{convert_into_seconds(item.end_time - item.start_time)}"
        )
        if done_time is not None:
            self.doneTime.setText(f"{convert_into_seconds(done_time)}")
            background = re.search(
                r"#playerBtns QPushButton {\n"
                r" {4}background-color: (?P<rgb>.+);\n"
                r" {4}padding: 5px 3px 5px 3px;\n}",
                main_window.centralwidget.styleSheet(),
                flags=re.MULTILINE,
            )
            if background:
                self.setStyleSheet(
                    f"""
                    #bookItems QSlider::add-page:horizontal {{
                        background: {background.group('rgb')};
                    }}
                    """
                )
        else:
            self.doneTime.hide()
            self.separator.hide()
            background = re.search(
                r"#bookItems QSlider::add-page:horizontal "
                r"{\n {4}background: (?P<rgb>.+);\n}",
                main_window.centralwidget.styleSheet(),
                flags=re.MULTILINE,
            )
            if background:
                self.setStyleSheet(
                    f"""
                    #bookItems QSlider::sub-page:horizontal {{
                        background: {background.group('rgb')};
                    }}
                    """
                )

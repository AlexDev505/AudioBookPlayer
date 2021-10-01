import config  # noqa
from drivers.akniga import AKnigaDriver
from drivers.knigavuhe import KnigaVUhe
from drivers.base import DownloadProcessHandler
from database import Books
import os

drv = AKnigaDriver()

book = drv.get_book("https://akniga.org/bogomazov-sergey-revolyuciya")

drv.download_book(book, DownloadProcessHandler())
books = Books(os.environ["DB_PATH"])
books.insert(**vars(book))

"""
Test Qt Frameless Window resizing with QSizeGrip
Maxwell Grady, September 2017.
"""
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *


class movable_label(QLabel):
    def __init__(self, parent):
        super().__init__(parent)

        self.parent = parent

        self.setStyleSheet("background-color: #ccc")
        self.setMinimumHeight(30)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self.parent.press_control == 0:
                self.pos = e.pos()
                self.main_pos = self.parent.pos()
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self.parent.cursor().shape() == Qt.ArrowCursor:
            self.last_pos = e.pos() - self.pos
            self.main_pos += self.last_pos
            self.parent.move(self.main_pos)
        # super(movable_label, self).mouseMoveEvent(e)


class main(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowFlags(Qt.FramelessWindowHint)
        self.central = QWidget()

        self.vbox = QVBoxLayout(self.central)
        self.vbox.addWidget(movable_label(self))
        self.vbox.addWidget(QPushButton("Click"))
        self.vbox.setAlignment(Qt.AlignTop)
        self.vbox.setSpacing(0)
        self.vbox.setContentsMargins(0, 0, 0, 0)

        self.press_control = 0

        self.setCentralWidget(self.central)
        self.resize(800, 500)
        self.show()

    def eventFilter(self, obj, e):
        # hovermoveevent
        if e.type() == 129:
            if self.press_control == 0:
                self.pos_control(e)  # cursor position control for cursor shape setup

        # mousepressevent
        if e.type() == 2:
            self.press_control = 1
            self.origin = self.mapToGlobal(e.pos())
            self.ori_geo = self.geometry()

        # mousereleaseevent
        if e.type() == 3:
            self.press_control = 0
            self.pos_control(e)

        # mosuemoveevent
        if e.type() == 5:
            if self.cursor().shape() != Qt.ArrowCursor:
                self.resizing(self.origin, e, self.ori_geo, self.value)

        return True

    def pos_control(self, e):
        rect = self.rect()
        top_left = rect.topLeft()
        top_right = rect.topRight()
        bottom_left = rect.bottomLeft()
        bottom_right = rect.bottomRight()
        pos = e.pos()

        # top catch
        if pos in QRect(
            QPoint(top_left.x() + 5, top_left.y()),
            QPoint(top_right.x() - 5, top_right.y() + 5),
        ):
            self.setCursor(Qt.SizeVerCursor)
            self.value = 1

        # bottom catch
        elif pos in QRect(
            QPoint(bottom_left.x() + 5, bottom_left.y()),
            QPoint(bottom_right.x() - 5, bottom_right.y() - 5),
        ):
            self.setCursor(Qt.SizeVerCursor)
            self.value = 2

        # right catch
        elif pos in QRect(
            QPoint(top_right.x() - 5, top_right.y() + 5),
            QPoint(bottom_right.x(), bottom_right.y() - 5),
        ):
            self.setCursor(Qt.SizeHorCursor)
            self.value = 3

        # left catch
        elif pos in QRect(
            QPoint(top_left.x() + 5, top_left.y() + 5),
            QPoint(bottom_left.x(), bottom_left.y() - 5),
        ):
            self.setCursor(Qt.SizeHorCursor)
            self.value = 4

        # top_right catch
        elif pos in QRect(
            QPoint(top_right.x(), top_right.y()),
            QPoint(top_right.x() - 5, top_right.y() + 5),
        ):
            self.setCursor(Qt.SizeBDiagCursor)
            self.value = 5

        # botom_left catch
        elif pos in QRect(
            QPoint(bottom_left.x(), bottom_left.y()),
            QPoint(bottom_left.x() + 5, bottom_left.y() - 5),
        ):
            self.setCursor(Qt.SizeBDiagCursor)
            self.value = 6

        # top_left catch
        elif pos in QRect(
            QPoint(top_left.x(), top_left.y()),
            QPoint(top_left.x() + 5, top_left.y() + 5),
        ):
            self.setCursor(Qt.SizeFDiagCursor)
            self.value = 7

        # bottom_right catch
        elif pos in QRect(
            QPoint(bottom_right.x(), bottom_right.y()),
            QPoint(bottom_right.x() - 5, bottom_right.y() - 5),
        ):
            self.setCursor(Qt.SizeFDiagCursor)
            self.value = 8

        # default
        else:
            self.setCursor(Qt.ArrowCursor)

    def resizing(self, ori, e, geo, value):
        # top_resize
        if self.value == 1:
            last = self.mapToGlobal(e.pos()) - ori
            first = geo.height()
            first -= last.y()
            Y = geo.y()
            Y += last.y()

            if first > self.minimumHeight():
                self.setGeometry(geo.x(), Y, geo.width(), first)

                # bottom_resize
        if self.value == 2:
            last = self.mapToGlobal(e.pos()) - ori
            first = geo.height()
            first += last.y()
            self.resize(geo.width(), first)

        # right_resize
        if self.value == 3:
            last = self.mapToGlobal(e.pos()) - ori
            first = geo.width()
            first += last.x()
            self.resize(first, geo.height())

        # left_resize
        if self.value == 4:
            last = self.mapToGlobal(e.pos()) - ori
            first = geo.width()
            first -= last.x()
            X = geo.x()
            X += last.x()

            if first > self.minimumWidth():
                self.setGeometry(X, geo.y(), first, geo.height())

        # top_right_resize
        if self.value == 5:
            last = self.mapToGlobal(e.pos()) - ori
            first_width = geo.width()
            first_height = geo.height()
            first_Y = geo.y()
            first_width += last.x()
            first_height -= last.y()
            first_Y += last.y()

            if first_height > self.minimumHeight():
                self.setGeometry(geo.x(), first_Y, first_width, first_height)

        # bottom_right_resize
        if self.value == 6:
            last = self.mapToGlobal(e.pos()) - ori
            first_width = geo.width()
            first_height = geo.height()
            first_X = geo.x()
            first_width -= last.x()
            first_height += last.y()
            first_X += last.x()

            if first_width > self.minimumWidth():
                self.setGeometry(first_X, geo.y(), first_width, first_height)

        # top_left_resize
        if self.value == 7:
            last = self.mapToGlobal(e.pos()) - ori
            first_width = geo.width()
            first_height = geo.height()
            first_X = geo.x()
            first_Y = geo.y()
            first_width -= last.x()
            first_height -= last.y()
            first_X += last.x()
            first_Y += last.y()

            if (
                first_height > self.minimumHeight()
                and first_width > self.minimumWidth()
            ):
                self.setGeometry(first_X, first_Y, first_width, first_height)

        # bottom_right_resize
        if self.value == 8:
            last = self.mapToGlobal(e.pos()) - ori
            first_width = geo.width()
            first_height = geo.height()
            first_width += last.x()
            first_height += last.y()

            self.setGeometry(geo.x(), geo.y(), first_width, first_height)


app = QApplication([])
window = main()
window.installEventFilter(window)
app.exec()

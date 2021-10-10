from __future__ import annotations

import os
import typing as ty

from PyQt5 import QtWidgets, QtCore, QtGui

from ui import UiMainWindow
from ui_functions import (
    add_book_page,
    book_page,
    control_panel,
    library,
    menu,
    sliders,
    window_geometry,
)
from database import Books

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QObject, QEvent
    from PyQt5.QtGui import QMovie
    from database import Book


class MainWindow(QtWidgets.QMainWindow, UiMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setupSignals()

        self.downloading = False  # Идёт ли процесс скачивания
        self.book: Book = ...

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
            lambda e: library.toggleFiltersPanel(self)
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

        # ADD BOOK PAGE
        self.searchNewBookBtn.clicked.connect(lambda e: add_book_page.search(self))

        # BOOK PAGE
        self.saveBtn.clicked.connect(lambda e: book_page.download_book(self, self.book))
        self.downloadBookBtn.clicked.connect(
            lambda e: book_page.download_book(self, self.book)
        )

    def openInfoPage(
        self,
        text: str = "",
        movie: QMovie = None,
        btn_text: str = "",
        btn_function: ty.Callable = None,
    ):
        self.infoPageLabel.setMovie(movie)
        self.infoPageLabel.setText(text)
        if movie:
            movie.start()
        self.infoPageBtn.setText(btn_text)
        if btn_function:
            self.infoPageBtn.clicked.connect(lambda: btn_function())
            self.infoPageBtn.show()
        else:
            self.infoPageBtn.hide()
        self.stackedWidget.setCurrentWidget(self.infoPage)

    def openBookPage(self, book: Book):
        self.titleLabel.setText(f"{book.author} - {book.name}")
        book_data = Books(os.environ["DB_PATH"]).filter(
            author=book.author, name=book.name
        )
        if not book_data:
            self.toggleFavoriteBtn.hide()
            self.deleteBtn.hide()
            self.changeDriverBtn.hide()
            self.saveBtn.show()
            self.playerContent.setCurrentWidget(self.needDownloadingPage)
        else:
            self.toggleFavoriteBtn.show()
            self.deleteBtn.show()
            self.changeDriverBtn.show()
            self.saveBtn.hide()
            self.playerContent.setCurrentWidget(self.playerPage)
            book = book_data

        self.authorLabel.setText(book.author)
        self.nameLabel.setText(book.name)
        self.readerLabel.setText(book.reader)
        self.durationLabel.setText(book.duration)
        self.description.setText(book.description)

        if not book_data:
            book_page.download_preview(self, book)
        else:
            cover_path = os.path.join(book.dir_path, "cover.jpg")
            if os.path.isfile(cover_path):
                pixmap = QtGui.QPixmap()
                pixmap.load(cover_path)
                self.bookCoverLg.setPixmap(pixmap)
            else:
                book_page.download_preview(self, book)

        self.stackedWidget.setCurrentWidget(self.bookPage)
        self.book = book

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        window_geometry.mouseEvent(self, event)

        return super(MainWindow, self).eventFilter(obj, event)

from __future__ import annotations

import os
import typing as ty

from PyQt5 import QtWidgets, QtCore, QtGui

from ui import UiMainWindow, UiBook, Item
from ui_functions import (
    add_book_page,
    book_page,
    content,
    control_panel,
    library,
    menu,
    sliders,
    window_geometry,
)
from database import Books
from database.tables.books import Status

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QObject, QEvent
    from PyQt5.QtGui import QMovie
    from database import Book
    from database.tables.books import BookItem


class MainWindow(QtWidgets.QMainWindow, UiMainWindow):
    def __init__(self):
        super(MainWindow, self).__init__()
        self.setupUi(self)

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.setupSignals()

        self.downloadable_book: Book = ...  # Книга, которую скачиваем
        self.book: Books = ...

        self.openLibraryPage()

        self.stackedWidget.oldSetCurrentWidget = self.stackedWidget.setCurrentWidget
        self.stackedWidget.setCurrentWidget = lambda page: content.setCurrentPage(
            self, page
        )

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
        sliders.prepareSlider(self.volumeSlider)

        self.speedSlider.valueChanged.connect(
            lambda value: control_panel.speedSliderHandler(self, value)
        )
        sliders.prepareSlider(self.speedSlider)

        book_page.prepareProgressBar(self.downloadingProgressBar)
        self.downloadingProgressBar.mousePressEvent = lambda e: self.openBookPage(
            self.downloadable_book
        )

        # ADD BOOK PAGE
        self.searchNewBookBtn.clicked.connect(lambda e: add_book_page.search(self))

        # BOOK PAGE
        self.saveBtn.clicked.connect(lambda e: book_page.downloadBook(self, self.book))
        self.downloadBookBtn.clicked.connect(
            lambda e: book_page.downloadBook(self, self.book)
        )
        self.deleteBtn.clicked.connect(lambda e: book_page.deleteBook(self))
        self.toggleFavoriteBtn.clicked.connect(lambda e: book_page.toggleFavorite(self))
        self.changeDriverBtn.clicked.connect(lambda e: book_page.changeDriver(self))
        self.stopDownloadingBtn.clicked.connect(
            lambda e: book_page.stopBookDownloading(self)
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
        item: BookItem

        self.titleLabel.setText(f"{book.author} - {book.name}")
        book_data = Books(os.environ["DB_PATH"]).filter(
            author=book.author, name=book.name
        )
        if not book_data:
            self.toggleFavoriteBtn.hide()
            self.deleteBtn.hide()
            self.changeDriverBtn.hide()
            if (
                self.downloadable_book is not ...
                and self.downloadable_book.url == book.url
            ):
                self.saveBtn.hide()
                self.playerContent.setCurrentWidget(self.downloadingPage)
            else:
                self.saveBtn.show()
                self.playerContent.setCurrentWidget(self.needDownloadingPage)
        else:
            self.toggleFavoriteBtn.show()
            self.deleteBtn.show()
            self.changeDriverBtn.show()
            self.saveBtn.hide()
            self.playerContent.setCurrentWidget(self.playerPage)
            book = book_data

            icon = QtGui.QIcon()
            if book.favorite:
                icon.addPixmap(
                    QtGui.QPixmap(":/other/star_fill.svg"),
                    QtGui.QIcon.Normal,
                    QtGui.QIcon.Off,
                )
            else:
                icon.addPixmap(
                    QtGui.QPixmap(":/other/star.svg"),
                    QtGui.QIcon.Normal,
                    QtGui.QIcon.Off,
                )
            self.toggleFavoriteBtn.setIcon(icon)

            # Очищаем от старых элементов
            for children in self.bookItemsLayout.children():
                if not isinstance(children, QtWidgets.QVBoxLayout):
                    children.hide()
                    children.deleteLater()
            for i in reversed(range(self.bookItemsLayout.layout().count())):
                item = self.bookItemsLayout.layout().itemAt(i)
                if isinstance(item, QtWidgets.QSpacerItem):
                    self.bookItemsLayout.layout().removeItem(item)

            for i, item in enumerate(book.items):
                if book.stop_flag.item == i:
                    Item(self, self.bookItemsLayout, item, book.stop_flag.time)
                    continue
                Item(self, self.bookItemsLayout, item)
            self.bookItems.scroll(0, 50 * book.stop_flag.item)
            QtCore.QTimer.singleShot(
                100,
                lambda: self.bookItems.verticalScrollBar().setValue(
                    book.stop_flag.item * 50
                ),
            )

            bookItemsSpacer = QtWidgets.QSpacerItem(
                40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            self.bookItemsLayout.layout().addItem(bookItemsSpacer)

        self.authorLabel.setText(book.author)
        self.nameLabel.setText(book.name)
        self.readerLabel.setText(book.reader)
        self.durationLabel.setText(book.duration)
        self.description.setText(book.description)

        book_page.loadPreview(self.bookCoverLg, (230, 230), book)

        self.book = book
        self.stackedWidget.setCurrentWidget(self.bookPage)

    def openLibraryPage(self):
        books: ty.List[Books] = Books(os.environ["DB_PATH"]).filter(return_list=True)

        for layout in [
            self.allBooksLayout,
            self.inProgressBooksLayout,
            self.listenedBooksLayout,
        ]:
            for children in layout.children():
                if not isinstance(children, QtWidgets.QVBoxLayout):
                    children.hide()
                    children.deleteLater()
            for i in reversed(range(layout.layout().count())):
                item = layout.layout().itemAt(i)
                if isinstance(item, QtWidgets.QSpacerItem):
                    layout.layout().removeItem(item)

        sizes = []
        for book in books:
            bookWidget = self._initBookWidget(self.allBooksLayout, book)
            sizes.append(
                bookWidget.titleLabel.sizeHint().width()
                + bookWidget.btnsFtame.sizeHint().width()
                + 300
            )
            if book.status == Status.started:
                self._initBookWidget(self.inProgressBooksLayout, book)
            elif book.status == Status.finished:
                self._initBookWidget(self.listenedBooksLayout, book)

        if not len(books):
            self.allBooksContainer.hide()
            self.allBooksPageNothing.show()
            if self.libraryFiltersPanel.width() != 25:
                self.toggleBooksFilterPanelBtn.click()
        else:
            self.library.setMinimumWidth(max(sizes))
            self.allBooksContainer.show()
            self.allBooksPageNothing.hide()
            allBooksContainerSpacer = QtWidgets.QSpacerItem(
                40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            self.allBooksLayout.layout().addItem(allBooksContainerSpacer)

        if len(self.inProgressBooksLayout.children()) < 2:
            self.inProgressBooksContainer.hide()
            self.inProsessBooksPageNothing.show()
        else:
            self.inProgressBooksContainer.show()
            self.inProsessBooksPageNothing.hide()
            inProgressBooksContainerSpacer = QtWidgets.QSpacerItem(
                40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            self.inProgressBooksLayout.layout().addItem(inProgressBooksContainerSpacer)

        if len(self.listenedBooksLayout.children()) < 2:
            self.listenedBooksContainer.hide()
            self.listenedBooksPageNothing.show()
        else:
            self.listenedBooksContainer.show()
            self.listenedBooksPageNothing.hide()
            listenedBooksContainerSpacer = QtWidgets.QSpacerItem(
                40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            self.listenedBooksLayout.layout().addItem(listenedBooksContainerSpacer)

        self.library.setCurrentWidget(self.allBooksPage)

        self.stackedWidget.setCurrentWidget(self.libraryPage)

    def _initBookWidget(self, parent: QtWidgets.QWidget, book: Books) -> UiBook:
        bookFrame = QtWidgets.QFrame(parent)
        bookWidget = UiBook()
        bookWidget.setupUi(bookFrame)

        bookWidget.titleLabel.setText(f"{book.author} - {book.name}")
        icon = QtGui.QIcon()
        if book.favorite:
            icon.addPixmap(
                QtGui.QPixmap(":/other/star_fill.svg"),
                QtGui.QIcon.Normal,
                QtGui.QIcon.Off,
            )
        else:
            icon.addPixmap(
                QtGui.QPixmap(":/other/star.svg"), QtGui.QIcon.Normal, QtGui.QIcon.Off
            )
        bookWidget.toggleFavoriteBtn.setIcon(icon)
        description = book.description.replace("\n", "")
        if len(description) > 250:
            description = description[:250]
            description = description[: description.rfind(" ")] + "..."
        bookWidget.description.setText(description)
        bookWidget.authorLabel.setText(book.author)
        bookWidget.readerLabel.setText(book.reader)
        bookWidget.durationLabel.setText(book.duration)
        if book.status == Status.finished:
            bookWidget.inProcessIcon.hide()
            bookWidget.progressLabel.setText("Прослушано")
        elif book.status == Status.started:
            bookWidget.finishedIcon.hide()
            item: BookItem
            total = sum([item.end_time - item.start_time for item in book.items])
            cur = (
                sum(
                    [
                        item.end_time - item.start_time
                        for i, item in enumerate(book.items)
                        if i < book.stop_flag.item
                    ]
                )
                + book.stop_flag.time
            )
            bookWidget.progressLabel.setText(
                f"{int(round(cur / (total / 100)))}% прослушано"
            )
        else:
            bookWidget.finishedIcon.hide()

        book_page.loadPreview(bookWidget.cover, (200, 200), book)
        bookWidget.deleteBtn.clicked.connect(lambda e: book_page.deleteBook(self, book))
        bookWidget.toggleFavoriteBtn.clicked.connect(
            lambda e: book_page.toggleFavorite(self, book)
        )

        bookWidget.frame.mousePressEvent = lambda e: self.openBookPage(book)
        parent.layout().addWidget(bookFrame)
        return bookWidget

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        window_geometry.mouseEvent(self, event)

        return super(MainWindow, self).eventFilter(obj, event)

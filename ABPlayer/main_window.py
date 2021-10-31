from __future__ import annotations

import os
import typing as ty

from PyQt5 import QtWidgets, QtCore, QtGui, QtMultimedia

from database import Books
from database.tables.books import Status
from ui import UiMainWindow, UiBook, Item
from ui_functions import (
    add_book_page,
    book_page,
    content,
    control_panel,
    filter_panel,
    library,
    marquee,
    menu,
    player,
    sliders,
    window_geometry,
)
import styles

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QObject, QEvent
    from database.tables.books import Book, BookItem


class MainWindow(QtWidgets.QMainWindow, UiMainWindow, player.MainWindowPlayer):
    def __init__(self):
        super(MainWindow, self).__init__()
        player.MainWindowPlayer.__init__(self)
        self.setupUi(self)

        self.centralwidget.setStyleSheet(
            styles.get_style_sheet(os.environ["theme"]) or styles.DEFAULT_STYLESHEET
        )

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.downloadable_book: Book = ...  # Книга, которую скачиваем
        self.book: Books = ...  # Открытая книга
        self.current_item_widget: Item = ...
        self.favorite_books_page: bool = False
        self.search_on: bool = False  # Нужно ли производить поиск по ключевым словам
        # Число запущенных потоков, скачивающих обложки книг
        self.download_cover_thread_count = 0

        # self.player = player.Player()

        self.setupSignals()
        self.openLibraryPage()

        marquee.prepareLabel(self, self.bookNameLabel)
        # marquee.prepareLabel(self, self.bookAuthorLabel)

    def setupSignals(self):
        # APPLICATION
        self.stackedWidget.setCurrentWidget = lambda page: content.setCurrentPage(
            self, page
        )

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
        self.clearSortAuthorBtn.clicked.connect(
            lambda e: filter_panel.resetAuthor(self)
        )
        self.invertSortBtn.clicked.connect(
            lambda e: filter_panel.toggleInvertSort(self)
        )
        self.sortBy.currentIndexChanged.connect(lambda e: self.openLibraryPage())
        self.sortAuthor.currentIndexChanged.connect(lambda e: self.openLibraryPage())
        self.searchBookBtn.clicked.connect(lambda e: filter_panel.search(self))

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
        self.progressToolsBtn.clicked.connect(
            lambda e: book_page.listeningProgressTools(self)
        )
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

        # PLAYER
        self.pastBtn.clicked.connect(lambda e: self.player.rewindToPast())
        self.futureBtn.clicked.connect(lambda e: self.player.rewindToFuture())
        self.playPauseBtnLg.clicked.connect(lambda e: self.player.playPause(self))
        self.playPauseBtn.clicked.connect(lambda e: self.player.setState(self))

    def openInfoPage(
        self,
        text: str = "",
        movie: QtGui.QMovie = None,
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

    def openLoadingPage(self):
        movie = QtGui.QMovie(":/other/loading.gif")
        movie.setScaledSize(QtCore.QSize(50, 50))
        self.openInfoPage(movie=movie)

    def openBookPage(self, book: Book):
        item: BookItem

        self.book = book

        book_data = Books(os.environ["DB_PATH"]).filter(
            author=self.book.author, name=self.book.name
        )
        if not book_data:  # Книга не зарегистрирована в бд
            self.progressFrame.hide()
            self.toggleFavoriteBtn.hide()
            self.deleteBtn.hide()
            self.changeDriverBtn.hide()
            if (
                self.downloadable_book is not ...
                and self.downloadable_book.url == self.book.url
            ):  # Эта книга в процессе скачивания
                self.saveBtn.hide()
                self.playerContent.setCurrentWidget(self.downloadingPage)
            else:
                self.saveBtn.show()
                self.playerContent.setCurrentWidget(self.needDownloadingPage)
        else:
            self.progressFrame.show()
            self.toggleFavoriteBtn.show()
            self.deleteBtn.show()
            self.changeDriverBtn.show()
            self.saveBtn.hide()
            self.playerContent.setCurrentWidget(self.playerPage)
            self.book = book_data

            if self.player.book is not ...:
                if self.book.url == self.player.book.url:
                    self.book = self.player.book

            # Устанавливаем иконку на кнопку "Добавить в избранное"
            icon = QtGui.QIcon()
            if self.book.favorite:
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

            # Иконка кнопки play/pause
            icon = QtGui.QIcon(
                ":/other/pause.svg"
                if self.player.player.state() == QtMultimedia.QMediaPlayer.PlayingState
                and self.book == self.player.book
                else ":/other/play.svg"
            )
            self.playPauseBtnLg.setIcon(icon)

            self.loadPlayer()

        self.titleLabel.setText(f"{self.book.author} - {self.book.name}")
        self.authorLabel.setText(self.book.author)
        self.nameLabel.setText(self.book.name)
        self.readerLabel.setText(self.book.reader)
        self.durationLabel.setText(self.book.duration)
        self.description.setText(self.book.description)

        # Загрузка обложки
        book_page.loadPreview(self, self.bookCoverLg, (230, 230), self.book)

        self.stackedWidget.setCurrentWidget(self.bookPage)

    def loadPlayer(self):
        # Отображаем прогресс прослушивания
        if self.book.status == Status.finished:
            self.progressLabel.setText("Прослушано")
            self.progressToolsBtn.setToolTip("Отметить как не прослушанное")
        else:
            self.progressLabel.setText(f"{self.book.listening_progress} прослушано")
            self.progressToolsBtn.setToolTip("Отметить как прослушанное")

        # Очищаем от старых элементов
        for children in self.bookItemsLayout.children():
            if not isinstance(children, QtWidgets.QVBoxLayout):
                children.hide()
                children.deleteLater()
        for i in reversed(range(self.bookItemsLayout.layout().count())):
            item = self.bookItemsLayout.layout().itemAt(i)
            if isinstance(item, QtWidgets.QSpacerItem):
                self.bookItemsLayout.layout().removeItem(item)

        # Инициализируем элементы
        for i, item in enumerate(self.book.items):
            if self.book.stop_flag.item == i:
                self.current_item_widget = Item(
                    self, self.bookItemsLayout, item, self.book.stop_flag.time
                )
                continue
            Item(self, self.bookItemsLayout, item)
        # Автоматически прокручиваем к текущему элементу
        self.bookItems.scroll(0, 50 * self.book.stop_flag.item)
        QtCore.QTimer.singleShot(
            250,
            lambda: self.bookItems.verticalScrollBar().setValue(
                self.book.stop_flag.item * 50
            ),
        )

        # Прижимаем элементы к верхнему краю
        bookItemsSpacer = QtWidgets.QSpacerItem(
            40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
        )
        self.bookItemsLayout.layout().addItem(bookItemsSpacer)

    def openLibraryPage(self, books_ids: ty.List[int] = None):
        if self.search_on and books_ids is None:
            filter_panel.search(self)
            return
        if books_ids is None:
            self.searchBookLineEdit.setText("")

        db = Books(os.environ["DB_PATH"])
        all_books = db.filter(return_list=True)  # Все книги

        # Фильтруем и сортируем книги
        filter_kwargs = {}

        # Только избранные
        if self.favorite_books_page:
            filter_kwargs["favorite"] = True

        # Фильтрация по автору
        author = self.sortAuthor.currentIndex()
        if author != 0:
            filter_kwargs["author"] = self.sortAuthor.currentText()

        books: ty.List[Books] = Books(os.environ["DB_PATH"]).filter(
            return_list=True, **filter_kwargs
        )
        if books_ids is not None:
            books = [book for book in books if book.id in books_ids]

        # Сортировка
        sort_by = self.sortBy.currentIndex()
        if sort_by == 0:  # По дате добавления
            books.reverse()  # Новые сверху
        elif sort_by == 1:  # По названию
            books.sort(key=lambda obj: obj.name)
        elif sort_by == 2:  # По автору
            books.sort(key=lambda obj: obj.author)

        # Если нужно, отображаем в обратном порядке
        if self.invertSortBtn.isChecked():
            books.reverse()

        # Удаляем старые элементы
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

        self.sortAuthor.currentIndexChanged.disconnect()
        self.sortAuthor.clear()
        self.sortAuthor.addItem("Все")
        authors = sorted(set(obj.author for obj in all_books))
        for author in authors:
            self.sortAuthor.addItem(author)
        if filter_kwargs.get("author"):
            self.sortAuthor.setCurrentIndex(
                authors.index(filter_kwargs.get("author")) + 1
            )
        self.sortAuthor.currentIndexChanged.connect(lambda e: self.openLibraryPage())

        sizes = []  # Размеры всех элементов
        for book in books:
            if self.player.book is not ...:
                if book.url == self.player.book:
                    book = self.player.book
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
        else:
            self.library.setMinimumWidth(max(sizes))  # Устанавливаем минимальный размер
            self.allBooksContainer.show()
            self.allBooksPageNothing.hide()
            # Прижимаем элементы к верхнему краю
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
            # Прижимаем элементы к верхнему краю
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
            # Прижимаем элементы к верхнему краю
            listenedBooksContainerSpacer = QtWidgets.QSpacerItem(
                40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding
            )
            self.listenedBooksLayout.layout().addItem(listenedBooksContainerSpacer)

        if self.stackedWidget.currentWidget() != self.libraryPage:
            self.library.setCurrentWidget(self.allBooksPage)
        self.stackedWidget.setCurrentWidget(self.libraryPage)

    def _initBookWidget(self, parent: QtWidgets.QWidget, book: Books) -> UiBook:
        bookFrame = QtWidgets.QFrame(parent)
        bookWidget = UiBook()
        bookWidget.setupUi(bookFrame)

        bookWidget.titleLabel.setText(f"{book.author} - {book.name}")
        description = book.description.replace("\n", "")
        if len(description) > 250:
            description = description[:250]
            description = description[: description.rfind(" ")] + "..."
        bookWidget.description.setText(description)
        bookWidget.authorLabel.setText(book.author)
        bookWidget.readerLabel.setText(book.reader)
        bookWidget.durationLabel.setText(book.duration)

        # Устанавливаем иконку на кнопку "Добавить в избранное"
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

        # Настраиваем прогресс прослушивания
        if book.status == Status.finished:
            bookWidget.inProcessIcon.hide()
            bookWidget.progressLabel.setText("Прослушано")
        elif book.status == Status.started:
            bookWidget.finishedIcon.hide()
            bookWidget.progressLabel.setText(f"{book.listening_progress} прослушано")
        else:
            bookWidget.finishedIcon.hide()

        # Загрузка обложки
        book_page.loadPreview(self, bookWidget.cover, (200, 200), book)

        # Настройка кнопок
        bookWidget.deleteBtn.clicked.connect(lambda e: book_page.deleteBook(self, book))
        bookWidget.toggleFavoriteBtn.clicked.connect(
            lambda e: book_page.toggleFavorite(self, book)
        )
        bookWidget.frame.mousePressEvent = lambda e: self.openBookPage(book)

        parent.layout().addWidget(bookFrame)
        return bookWidget

    def setLock(self, value: bool) -> None:
        """
        Блокирует/разблокирует интерфейс.
        Используется при загрузке данных.
        :param value: True или False.
        """
        self.btnGroupFrame.setDisabled(value)
        self.btnGroupFrame_2.setDisabled(value)
        self.downloadingProgressBar.setDisabled(value)
        self.overlayBtn.setDisabled(value)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        window_geometry.mouseEvent(self, event)

        return super(MainWindow, self).eventFilter(obj, event)

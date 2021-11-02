"""

Главное окно приложения.
Соединяет весь функционал.

"""

from __future__ import annotations

import os
import typing as ty
import webbrowser

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, QSize, QTimer, Qt
from PyQt5.QtGui import QCloseEvent, QFontMetrics, QIcon, QMovie
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import (
    QFrame,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

import styles
import temp_file
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
    settings_page,
    sliders,
    window_geometry,
)

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QEvent, QObject
    from database.tables.books import Book


class MainWindow(QMainWindow, UiMainWindow, player.MainWindowPlayer):
    def __init__(self):
        super(MainWindow, self).__init__()
        player.MainWindowPlayer.__init__(self)
        self.setupUi(self)

        # Применяем настройки темы
        self.centralwidget.setStyleSheet(styles.get_style_sheet(os.environ["theme"]))

        # Окно без рамок
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.downloadable_book: Book = ...  # Книга, которую скачиваем
        self.book: Books = ...  # Открытая книга
        self.current_item_widget: Item = ...  # Виджет главы
        self.favorite_books_page: bool = (
            False  # Находимся ли мы на странице избранных книг
        )
        self.search_on: bool = False  # Нужно ли производить поиск по ключевым словам
        # Число запущенных потоков, скачивающих обложки книг
        self.download_cover_thread_count = 0

        self.setupSignals()

        # Модифицируем QLabel, превращая его в marquee
        marquee.prepareLabel(self, self.bookNameLabel)

        # Загружаем данные из прошлой сессии
        temp = temp_file.load()
        last_listened_book_id = temp.get("last_listened_book_id")
        last_volume = temp.get("last_volume")

        # Загружаем последнюю прослушиваемую книгу
        if last_listened_book_id is not None:
            book = Books(os.environ["DB_PATH"]).filter(id=last_listened_book_id)
            if book:
                self.book = book
                self.player.book = book
                self.loadMiniPlayer()
            else:
                temp_file.delete_items("last_listened_book_id")

        # Устанавливаем последнюю громкость воспроизведения
        if last_volume is not None:
            if 0 <= last_volume <= 100:
                self.player.player.setVolume(last_volume)
                self.volumeSlider.setValue(last_volume)
            else:
                temp_file.delete_items("last_volume")

        self.openLibraryPage()  # При запуске приложения открываем библиотеку

        # Указываем версию приложения
        self.appBuildVersionLabel.setText(f"Версия: {os.environ['version']}")

        # Заполняем QComboBox темами
        for style in styles.styles:
            self.themeSelecror.addItem(style)
        if not len(styles.styles):
            self.themeSelecror.addItem("Тёмная")
            self.themeSelecror.setCurrentIndex(0)
        else:
            if os.environ["theme"] in styles.styles:
                self.themeSelecror.setCurrentIndex(
                    list(styles.styles.keys()).index(os.environ["theme"])
                )
            else:
                if "Тёмная" in styles.styles:
                    self.themeSelecror.removeItem(
                        list(styles.styles.keys()).index("Тёмная")
                    )
                self.themeSelecror.insertItem(0, "Тёмная")
                self.themeSelecror.setCurrentIndex(0)
            self.themeSelecror.currentIndexChanged.connect(
                lambda e: settings_page.changeTheme(self)
            )
        # Устанавливаем минимальный размер QComboBox
        fm = QFontMetrics(self.themeSelecror.font())
        items: ty.List[int] = []
        for i in range(self.themeSelecror.count()):
            items.append(fm.width(self.themeSelecror.itemText(i)) + 80)
        self.themeSelecror.setMinimumWidth(max(items))

    def setupSignals(self) -> None:
        # APPLICATION
        self.stackedWidget.setCurrentWidget = lambda page: content.setCurrentPage(
            self, page
        )  # Модифицируем метод изменения страницы

        self.closeAppBtn.clicked.connect(self.close)  # Кнопка закрытия приложения
        self.fullscreenAppBtn.clicked.connect(
            lambda: window_geometry.toggleFullScreen(self)
        )  # Кнопка открытия приложения в полный экран
        self.minimizeAppBtn.clicked.connect(self.showMinimized)  # Кнопка сворачивания

        # Подготавливаем область, отвечающую за перемещение окна
        window_geometry.prepareDragZone(self, self.logo)

        # MENU
        self.menuBtn.clicked.connect(lambda e: menu.toggleMenu(self))
        self.menuButtons.buttonClicked.connect(
            lambda btn: menu.buttonsHandler(self, btn)
        )  # Нажатие на кнопки в меню

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
        self.searchBookLineEdit.returnPressed.connect(lambda: filter_panel.search(self))

        # CONTROL PANEL
        self.controlPanelButtons.buttonClicked.connect(
            lambda btn: control_panel.buttonsHandler(self, btn)
        )

        self.volumeSlider.valueChanged.connect(
            lambda value: control_panel.volumeSliderHandler(self, value)
        )
        sliders.prepareSlider(self.volumeSlider)
        self.volumeSlider.mouseReleaseEvent = (
            lambda e: control_panel.volumeSliderMouseReleaseEvent(self, e)
        )

        self.speedSlider.valueChanged.connect(
            lambda value: control_panel.speedSliderHandler(self, value)
        )
        sliders.prepareSlider(self.speedSlider)

        book_page.prepareProgressBar(self.downloadingProgressBar)
        self.downloadingProgressBar.mousePressEvent = lambda e: self.openBookPage(
            self.downloadable_book
        )  # Нажатие на полосу загрузки

        # ADD BOOK PAGE
        self.searchNewBookBtn.clicked.connect(lambda e: add_book_page.search(self))
        self.searchNewBookLineEdit.returnPressed.connect(
            lambda: add_book_page.search(self)
        )

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
        self.bookPreview.mousePressEvent = (
            lambda e: control_panel.bookPreviewMousePressEvent(self, e)
        )

        # PLAYER
        self.pastBtn.clicked.connect(lambda e: self.player.rewindToPast())
        self.futureBtn.clicked.connect(lambda e: self.player.rewindToFuture())
        self.playPauseBtnLg.clicked.connect(lambda e: self.player.playPause(self))
        self.playPauseBtn.clicked.connect(lambda e: self.player.setState(self))

        # SETTINGS PAGE
        self.developerBtn.clicked.connect(
            lambda e: webbrowser.open_new_tab("https://github.com/AlexDev-py")
        )
        self.projectPageBtn.clicked.connect(
            lambda e: webbrowser.open_new_tab(
                "https://github.com/AlexDev-py/AudioBookPlayer"
            )
        )

        self.openDirWithBooksBtn.clicked.connect(
            lambda e: os.startfile(os.environ["books_folder"])
        )
        self.setDirWithBooksBtn.clicked.connect(
            lambda e: settings_page.setDirWithBooks(self)
        )

    def openInfoPage(
        self,
        text: str = "",
        movie: QMovie = None,
        btn_text: str = "",
        btn_function: ty.Callable = None,
    ) -> None:
        """
        Открывает информационную страницу.
        :param text: Сообщение.
        :param movie: Анимация.
        :param btn_text: Текст на кнопке.
        :param btn_function: Функция кнопки.
        """
        self.infoPageMovie.setMovie(movie)
        self.infoPageLabel.clear()
        self.infoPageLabel.setAlignment(Qt.AlignCenter)
        self.infoPageLabel.insertPlainText(text)
        if movie:
            self.infoPageLabel.hide()
            self.infoPageMovie.show()
            movie.start()
        else:
            self.infoPageMovie.hide()
            self.infoPageLabel.show()
        self.infoPageBtn.setText(btn_text)
        if btn_function:
            try:
                self.infoPageBtn.clicked.disconnect()
            except TypeError:
                pass
            self.infoPageBtn.clicked.connect(lambda: btn_function())
            self.infoPageBtn.show()
        else:
            self.infoPageBtn.hide()
        self.stackedWidget.setCurrentWidget(self.infoPage)

    def openLoadingPage(self) -> None:
        """
        Открывает страницу загрузки.
        """
        movie = QMovie(":/other/loading.gif")
        movie.setScaledSize(QSize(50, 50))
        self.openInfoPage(movie=movie)

    def openBookPage(self, book: ty.Union[Book, Books]) -> None:
        """
        Открывает страницу книги.
        :param book: Экземпляр скачанной или не скачанной книги.
        """
        self.book = book

        book_data = Books(os.environ["DB_PATH"]).filter(
            author=self.book.author, name=self.book.name
        )  # Получаем информацию о книге из бд
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

            # Если эту книгу сейчас слушает пользователь
            if self.player.book is not ...:
                if self.book.url == self.player.book.url:
                    self.book = self.player.book

            # Устанавливаем иконку на кнопку "Добавить в избранное"
            icon = QIcon(
                ":/other/star_fill.svg" if self.book.favorite else ":/other/star.svg"
            )
            self.toggleFavoriteBtn.setIcon(icon)

            # Иконка кнопки play/pause
            icon = QIcon(
                ":/other/pause.svg"
                if self.player.player.state() == QMediaPlayer.PlayingState
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

    def loadPlayer(self) -> None:
        """
        Обновляет плеер.
        """
        # Отображаем прогресс прослушивания
        if self.book.status == Status.finished:
            self.progressLabel.setText("Прослушано")
            self.progressToolsBtn.setToolTip("Отметить как не прослушанное")
        else:
            self.progressLabel.setText(f"{self.book.listening_progress} прослушано")
            self.progressToolsBtn.setToolTip("Отметить как прослушанное")

        # Очищаем от старых элементов
        for children in self.bookItemsLayout.children():
            if not isinstance(children, QVBoxLayout):
                children.hide()
                children.deleteLater()
        for i in reversed(range(self.bookItemsLayout.layout().count())):
            item = self.bookItemsLayout.layout().itemAt(i)
            if isinstance(item, QSpacerItem):
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
        QTimer.singleShot(
            250,
            lambda: self.bookItems.verticalScrollBar().setValue(
                self.book.stop_flag.item * 50
            ),
        )

        # Прижимаем элементы к верхнему краю
        bookItemsSpacer = QSpacerItem(
            40, 20, QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.bookItemsLayout.layout().addItem(bookItemsSpacer)

    def loadMiniPlayer(self) -> None:
        """
        Открывает мини плеер.
        Обновляет в нем данные.
        """
        if self.miniPlayerFrame.maximumWidth() == 0:
            self.miniPlayerFrame.player_animation = QPropertyAnimation(
                self.miniPlayerFrame, b"maximumWidth"
            )
            self.miniPlayerFrame.player_animation.setStartValue(0)
            self.miniPlayerFrame.player_animation.setEndValue(300)
            self.miniPlayerFrame.player_animation.setEasingCurve(
                QEasingCurve.InOutQuart
            )
            self.miniPlayerFrame.player_animation.finished.connect(
                lambda: self.miniPlayerFrame.__dict__.__delitem__("player_animation")
            )  # Удаляем анимацию
            self.miniPlayerFrame.player_animation.start()

        self.bookNameLabel.setText(self.player.book.name)
        self.bookAuthorLabel.setText(self.player.book.author)
        book_page.loadPreview(self, self.bookCover, (60, 60), self.player.book)

    def openLibraryPage(self, books_ids: ty.List[int] = None) -> None:
        """
        Открывает страницу библиотеки.
        :param books_ids: ID книг, которые прошли фильтрацию.
        """
        # Возникает при изменении параметров сортировки во время
        # поиска книг по ключевым словам
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
        )  # Запрос к бд
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

        # Заполняем QComboBox авторами
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

        # Удаляем старые элементы
        for layout in [
            self.allBooksLayout,
            self.inProgressBooksLayout,
            self.listenedBooksLayout,
        ]:
            for children in layout.children():
                if not isinstance(children, QVBoxLayout):
                    children.hide()
                    children.deleteLater()
            for i in reversed(range(layout.layout().count())):
                item = layout.layout().itemAt(i)
                if isinstance(item, QSpacerItem):
                    layout.layout().removeItem(item)

        sizes = []  # Размеры всех элементов
        # Инициализируем элементы
        for book in books:
            if self.player.book is not ...:
                if book.url == self.player.book.url:
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
            allBooksContainerSpacer = QSpacerItem(
                40, 20, QSizePolicy.Expanding, QSizePolicy.Expanding
            )
            self.allBooksLayout.layout().addItem(allBooksContainerSpacer)

        if len(self.inProgressBooksLayout.children()) < 2:
            self.inProgressBooksContainer.hide()
            self.inProsessBooksPageNothing.show()
        else:
            self.inProgressBooksContainer.show()
            self.inProsessBooksPageNothing.hide()
            # Прижимаем элементы к верхнему краю
            inProgressBooksContainerSpacer = QSpacerItem(
                40, 20, QSizePolicy.Expanding, QSizePolicy.Expanding
            )
            self.inProgressBooksLayout.layout().addItem(inProgressBooksContainerSpacer)

        if len(self.listenedBooksLayout.children()) < 2:
            self.listenedBooksContainer.hide()
            self.listenedBooksPageNothing.show()
        else:
            self.listenedBooksContainer.show()
            self.listenedBooksPageNothing.hide()
            # Прижимаем элементы к верхнему краю
            listenedBooksContainerSpacer = QSpacerItem(
                40, 20, QSizePolicy.Expanding, QSizePolicy.Expanding
            )
            self.listenedBooksLayout.layout().addItem(listenedBooksContainerSpacer)

        if self.stackedWidget.currentWidget() != self.libraryPage:
            self.library.setCurrentWidget(self.allBooksPage)
        self.stackedWidget.setCurrentWidget(self.libraryPage)

    def _initBookWidget(self, parent: QWidget, book: Books) -> UiBook:
        """
        Инициализирует виджет книги.
        :param parent: Виджет, в которые нужно поместить.
        :param book: Экземпляр скачанной книги.
        :return: Экземпляр виджета книги.
        """
        bookFrame = QFrame(parent)
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
        icon = QIcon(":/other/star_fill.svg" if book.favorite else ":/other/star.svg")
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
        Используется при загрузке цданных.
        :param value: True или False.
        """
        self.btnGroupFrame.setDisabled(value)
        self.btnGroupFrame_2.setDisabled(value)
        self.downloadingProgressBar.setDisabled(value)
        self.overlayBtn.setDisabled(value)
        self.bookPreview.setDisabled(value)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        window_geometry.mouseEvent(self, event)

        return super(MainWindow, self).eventFilter(obj, event)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.downloadable_book is not ...:
            if (
                QMessageBox.question(
                    self,
                    "Выход",
                    "Прогресс скачивания книги сброситься.\n"
                    "Вы действительно хотите закрыть приложение?",
                )
                == QMessageBox.Yes
            ):
                downloadable_book: Book = self.DownloadBookWorker.terminate()
                book_page.DeleteBookWorker(self, downloadable_book).worker()
                event.accept()
            else:
                event.ignore()

"""

Главное окно приложения.
Соединяет весь функционал.

"""

from __future__ import annotations

import os
import typing as ty
import webbrowser

from PyQt5.QtCore import QEasingCurve, QPropertyAnimation, QSize, QTimer, Qt
from PyQt5.QtGui import QCloseEvent, QColor, QFontMetrics, QIcon, QMovie, QKeySequence
from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QMainWindow,
    QMessageBox,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QShortcut,
    QWidget,
)
from loguru import logger

import styles
import temp_file
from database import Books
from database.tables.books import Status
from tools import pretty_view, trace_book_data, debug_book_data
from ui import Item, UiBook, UiMainWindow
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
        logger.trace("Initialization of the main window")
        super(MainWindow, self).__init__()
        player.MainWindowPlayer.__init__(self)
        self.setupUi(self)
        self.overlayBtn.hide()

        # Применяем настройки темы
        self.centralwidget.setStyleSheet(styles.get_style_sheet(os.environ["theme"]))

        # Окно без рамок
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)

        # Тень вокруг окна
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Оставляем область вокруг окна, в котором будет отображена тень
        self.centralwidget.layout().setContentsMargins(15, 15, 15, 15)
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)  # Размытие
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(0)  # Смещение
        self.centralwidget.setGraphicsEffect(self.shadow)

        self.downloadable_book: Book = ...  # Книга, которую скачиваем
        self.book: Books = ...  # Открытая книга
        self.current_item_widget: Item = ...  # Виджет главы
        self.favorite_books_page: bool = (
            False  # Находимся ли мы на странице избранных книг
        )
        self.search_on: bool = False  # Нужно ли производить поиск по ключевым словам
        # Число запущенных потоков, скачивающих обложки книг
        self.download_cover_thread_count = 0

        self.cur_books_in_all_container_count = 0
        self.cur_books_in_progress_container_count = 0
        self.cur_books_in_listened_container_count = 0
        self.cur_books = []

        self.setupSignals()

        # Определяем горячие клавиши
        self.CtrlPShortcut = QShortcut(QKeySequence("Ctrl+P"), self)
        self.CtrlFShortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.CtrlBShortcut = QShortcut(QKeySequence("Ctrl+B"), self)
        self.hotkeys = False

        # Модифицируем QLabel, превращая его в marquee
        marquee.prepareLabel(self, self.bookNameLabel)

        # Загружаем данные из прошлой сессии
        temp = temp_file.load()
        last_listened_book_id = temp.get("last_listened_book_id")
        last_volume = temp.get("last_volume")

        # Загружаем последнюю прослушиваемую книгу
        if last_listened_book_id is not None:
            logger.trace(f"Loading last book. Book id: {last_listened_book_id}")
            book = Books(os.environ["DB_PATH"]).filter(id=last_listened_book_id)
            if book:
                self.book = book
                self.player.book = book
                self.loadMiniPlayer()
            else:
                logger.debug("The last book is not registered")
                temp_file.delete_items("last_listened_book_id")

        # Устанавливаем последнюю громкость воспроизведения
        if last_volume is not None:
            logger.trace(f"Loading last volume. Value {last_volume}")
            if 0 <= last_volume <= 100:
                self.player.player.setVolume(last_volume)
                self.volumeSlider.setValue(last_volume)
            else:
                logger.debug("Invalid last volume")
                temp_file.delete_items("last_volume")

        self.openLibraryPage()  # При запуске приложения открываем библиотеку

        # Указываем версию приложения
        self.appBuildVersionLabel.setText(f"Версия: {os.environ['version']}")

        # Заполняем QComboBox темами
        for style in styles.styles:
            self.themeSelecror.addItem(style)
        if not len(styles.styles):
            logger.debug("No themes found")
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

        fm = QFontMetrics(self.dirWithBooksBtn.font())
        os.environ["MENU_WIDTH"] = str(int(fm.width(self.dirWithBooksBtn.text()) * 1.5))
        self.menuFrame.setMinimumWidth(int(os.environ["MENU_WIDTH"]))

    def setupSignals(self) -> None:
        logger.trace("Setting main window signals")
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

        self.allBooksContainer.verticalScrollBar().valueChanged.connect(
            lambda x: (
                self.addBooksToContainer(self.allBooksContainer, self.allBooksLayout)
            )
            if self.allBooksContainer.verticalScrollBar().maximum() == x
            else None
        )
        self.inProgressBooksContainer.verticalScrollBar().valueChanged.connect(
            lambda x: (
                self.addBooksToContainer(
                    self.inProgressBooksContainer, self.inProgressBooksLayout
                )
            )
            if self.allBooksContainer.verticalScrollBar().maximum() == x
            else None
        )
        self.listenedBooksContainer.verticalScrollBar().valueChanged.connect(
            lambda x: (
                self.addBooksToContainer(
                    self.listenedBooksContainer, self.listenedBooksLayout
                )
            )
            if self.allBooksContainer.verticalScrollBar().maximum() == x
            else None
        )

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
        self.speedSlider.mouseReleaseEvent = (
            lambda e: control_panel.speedSliderMouseReleaseEvent(self, e)
        )

        book_page.prepareProgressBar(self.downloadingProgressBar)
        self.downloadingProgressBar.mousePressEvent = lambda e: self.openBookPage(
            self.downloadable_book
        )  # Нажатие на полосу загрузки

        # ADD BOOK PAGE
        self.searchNewBookBtn.clicked.connect(lambda e: add_book_page.search(self))
        self.searchNewBookLineEdit.returnPressed.connect(
            lambda: add_book_page.search(self)
        )
        self.openSiteBtn.clicked.connect(
            lambda: webbrowser.open_new_tab("https://knigavuhe.org/")
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
            lambda e: settings_page.openDirWithBooks()
        )
        self.setDirWithBooksBtn.clicked.connect(
            lambda e: settings_page.setDirWithBooks(self)
        )

    def setupHotKeys(self) -> None:
        self.CtrlPShortcut.activated.connect(lambda: self.player.setState(self))
        self.CtrlFShortcut.activated.connect(lambda: self.player.rewindToFuture())
        self.CtrlBShortcut.activated.connect(lambda: self.player.rewindToPast())

    @logger.catch
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
        logger.debug("Opening the info page")
        logger.opt(colors=True).debug(
            "Info page content: "
            + pretty_view(
                dict(
                    text=text,
                    movie=True if movie else None,
                    btn_text=btn_text,
                    btn_function=True if btn_function else None,
                )
            ),
        )
        self.infoPageMovie.setMovie(movie)  # Устанавливаем анимацию
        self.infoPageLabel.clear()  # Очищаем текстовое поле
        self.infoPageLabel.setAlignment(Qt.AlignCenter)  # Центрирование текста
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
            try:  # Отключаем обработчик нажатия на кнопку
                self.infoPageBtn.clicked.disconnect()
            except TypeError:  # Возникает если обработчик не установлен
                pass
            self.infoPageBtn.clicked.connect(lambda: btn_function())
            self.infoPageBtn.show()
        else:
            self.infoPageBtn.hide()
        self.stackedWidget.setCurrentWidget(self.infoPage)
        logger.debug("Info page is open")

    def openLoadingPage(self) -> None:
        """
        Открывает страницу загрузки.
        """
        movie = QMovie(":/other/loading.gif")
        movie.setScaledSize(QSize(50, 50))
        self.openInfoPage(movie=movie)

    @logger.catch
    def openBookPage(self, book: ty.Union[Book, Books]) -> None:
        """
        Открывает страницу книги.
        :param book: Экземпляр скачанной или не скачанной книги.
        """
        logger.debug("Opening a book page")
        logger.opt(colors=True).trace(trace_book_data(book))
        logger.opt(colors=True).debug(debug_book_data(book))
        self.book = book

        book_data = Books(os.environ["DB_PATH"]).filter(
            author=self.book.author, name=self.book.name
        )  # Получаем информацию о книге из бд
        if not book_data:  # Книга не зарегистрирована в бд
            logger.debug("Book is not registered")
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
        logger.debug("Book page is open")

    @logger.catch
    def loadPlayer(self) -> None:
        """
        Обновляет плеер.
        """
        logger.trace("Loading the player")
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

    @logger.catch
    def loadMiniPlayer(self) -> None:
        """
        Открывает мини плеер.
        Обновляет в нем данные.
        """
        logger.trace("Loading the mini player")
        if not self.hotkeys:
            self.setupHotKeys()
            self.hotkeys = True

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

    def closeMiniPlayer(self) -> None:
        self.miniPlayerFrame.player_animation = QPropertyAnimation(
            self.miniPlayerFrame, b"maximumWidth"
        )
        self.miniPlayerFrame.player_animation.setStartValue(300)
        self.miniPlayerFrame.player_animation.setEndValue(0)
        self.miniPlayerFrame.player_animation.setEasingCurve(QEasingCurve.InOutQuart)
        self.miniPlayerFrame.player_animation.finished.connect(
            lambda: self.miniPlayerFrame.__dict__.__delitem__("player_animation")
        )  # Удаляем анимацию
        self.miniPlayerFrame.player_animation.start()
        temp_file.delete_items("last_listened_book_id")

    @logger.catch
    def openLibraryPage(self, books_ids: ty.List[int] = None) -> None:
        """
        Открывает страницу библиотеки.
        :param books_ids: ID книг, которые прошли фильтрацию по ключевым словам.
        """
        # Возникает при изменении параметров сортировки во время
        # поиска книг по ключевым словам
        if self.search_on and books_ids is None:
            filter_panel.search(self)
            return
        if books_ids is None:
            self.searchBookLineEdit.setText("")

        logger.debug("Opening library")
        self.libraryBtn.setDisabled(True)

        db = Books(os.environ["DB_PATH"])
        all_books = db.filter(return_list=True)  # Все книги

        # Заполняем QComboBox авторами
        self.sortAuthor.currentIndexChanged.disconnect()
        current_author = self.sortAuthor.currentText()
        self.sortAuthor.clear()
        self.sortAuthor.addItem("Все")
        authors = sorted(set(obj.author for obj in all_books))
        for author in authors:
            self.sortAuthor.addItem(author)
        if current_author in authors:
            self.sortAuthor.setCurrentIndex(authors.index(current_author) + 1)
        self.sortAuthor.currentIndexChanged.connect(lambda e: self.openLibraryPage())

        self.allBooksContainer.verticalScrollBar().setValue(0)

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

        # Фильтруем и сортируем книги
        filter_kwargs = {}

        # Только избранные
        if self.favorite_books_page:
            filter_kwargs["favorite"] = True

        # Фильтрация по автору
        author = self.sortAuthor.currentIndex()
        if author != 0:
            filter_kwargs["author"] = self.sortAuthor.currentText()

        logger.opt(colors=True).debug(
            "Filter kwargs: " + pretty_view({**filter_kwargs, "books_ids": books_ids}),
        )

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

        self.cur_books = books
        logger.opt(colors=True).trace("Books: " + pretty_view(books))
        logger.opt(colors=True).debug(f"Books: <y><list ({len(books)} objects)></y>")

        self.cur_books_in_all_container_count = 0
        self.cur_books_in_listened_container_count = 0
        self.cur_books_in_progress_container_count = 0

        self.addBooksToContainer(self.allBooksContainer, self.allBooksLayout)
        self.addBooksToContainer(
            self.inProgressBooksContainer, self.inProgressBooksLayout
        )
        self.addBooksToContainer(self.listenedBooksContainer, self.listenedBooksLayout)

        QTimer.singleShot(150, lambda: self.libraryBtn.setDisabled(False))

        if self.stackedWidget.currentWidget() != self.libraryPage:
            self.library.setCurrentWidget(self.allBooksPage)
        self.stackedWidget.setCurrentWidget(self.libraryPage)

        logger.debug("Library is open")

    def addBooksToContainer(self, container: QWidget, layout: QWidget):
        if layout == self.inProgressBooksLayout:
            books = [book for book in self.cur_books if book.status == Status.started]
        elif layout == self.listenedBooksLayout:
            books = [book for book in self.cur_books if book.status == Status.finished]
        else:
            books = self.cur_books

        if layout == self.inProgressBooksLayout:
            start = self.cur_books_in_progress_container_count
            if self.cur_books_in_progress_container_count >= len(books):
                return
            self.cur_books_in_progress_container_count += 6
        elif layout == self.listenedBooksLayout:
            start = self.cur_books_in_listened_container_count
            if self.cur_books_in_listened_container_count >= len(books):
                return
            self.cur_books_in_listened_container_count += 6
        else:
            start = self.cur_books_in_all_container_count
            if self.cur_books_in_all_container_count >= len(books):
                return
            self.cur_books_in_all_container_count += 6
        books = books[start : start + 6]

        widths = [self.library.sizeHint().width()]  # Ширина всех элементов
        # Инициализируем элементы
        for book in books:
            if self.player.book is not ...:
                if book.url == self.player.book.url:
                    book = self.player.book
            print(layout, book)
            bookWidget = self._initBookWidget(layout, book)
            widths.append(
                bookWidget.titleLabel.sizeHint().width()
                + bookWidget.btnsFtame.sizeHint().width()
                + 300
            )

        if not len(books):
            container.hide()
            if container == self.inProgressBooksContainer:
                self.inProsessBooksPageNothing.show()
            elif container == self.listenedBooksContainer:
                self.listenedBooksPageNothing.show()
            else:
                self.allBooksPageNothing.show()
        else:
            self.library.setMinimumWidth(
                max(widths)
            )  # Устанавливаем минимальный размер
            container.show()
            if container == self.inProgressBooksContainer:
                self.inProsessBooksPageNothing.hide()
            elif container == self.listenedBooksContainer:
                self.listenedBooksPageNothing.hide()
            else:
                self.allBooksPageNothing.hide()
            # Прижимаем элементы к верхнему краю
            allBooksContainerSpacer = QSpacerItem(
                40, 20, QSizePolicy.Expanding, QSizePolicy.Expanding
            )
            layout.layout().addItem(allBooksContainerSpacer)

    @logger.catch
    def _initBookWidget(self, parent: QWidget, book: Books) -> UiBook:
        """
        Инициализирует виджет книги.
        :param parent: Виджет, в которые нужно поместить.
        :param book: Экземпляр скачанной книги.
        :return: Экземпляр виджета книги.
        """
        logger.trace(
            "Initialization of the book widget. "
            f"Parent: {parent.objectName()}. {book.id=}"
        )
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
        Используется при загрузке данных.
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

    @logger.catch()
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
                return

        # Удаляем таблицу с книгами
        db = Books(os.environ["DB_PATH"])
        db.api.execute("DROP TABLE books")
        db.api.commit()

        logger.info("Closing the application")

        # При закрытии приложения, плеер сбрасывает позицию на 0,
        # из-за этого точка остановки сохраняется в бд.
        # Так же сбрасываем последнее сохранение, тогда точка остановки не сохранится.
        self.reset_last_save()

from __future__ import annotations

import os
import ssl
import typing as ty
import urllib.request

from PyQt5.QtCore import (
    Qt,
    QSize,
    QEvent,
    QThread,
    QObject,
    pyqtSignal,
    QBasicTimer,
    QEasingCurve,
    QPropertyAnimation,
)
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtWidgets import QMessageBox, QToolTip, QProgressBar

from database import Books
from drivers import drivers, BaseDownloadProcessHandler

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from PyQt5.QtWidgets import QLabel
    from main_window import MainWindow
    from database import Book


def convert_into_bits(bits: int) -> str:
    """
    :param bits: Число битов.
    :return: Строка вида <Число> <Единица измерения>
    """
    postfixes = ["КБ", "МБ", "ГБ"]
    if bits >= 2 ** 33:
        return f"{round(bits / 2 ** 33, 3)} {postfixes[-1]}"
    elif bits >= 2 ** 23:
        return f"{round(bits / 2 ** 23, 2)} {postfixes[-2]}"
    elif bits >= 2 ** 13:
        return f"{round(bits / 2 ** 13, 1)} {postfixes[-3]}"


class Cache(object):
    """
    Кэш.
    Временно хранит обложки книг. (до 4-х штук)
    """

    cache = {}

    @classmethod
    def get(cls, item: str) -> QPixmap:
        """
        :param item: Ссылка на картинку.
        :return: Экземпляр QPixmap.
        """
        return cls.cache.get(item)

    @classmethod
    def set(cls, key: str, value: QPixmap) -> None:
        """
        Добавляет картинку в кэш.
        :param key: Ссылка на картинку.
        :param value: Экземпляр QPixmap.
        """
        if len(cls.cache) >= 4:
            del cls.cache[list(cls.cache.keys())[0]]
        cls.cache[key] = value


class DownloadPreviewWorker(QObject):
    """
    Реализует скачивание обложки книги.
    При успешном скачивании обложка устанавливается в указанный QLabel.
    При ошибке скачивания указанный QLabel скрывается.
    """

    finished: QtCore.pyqtSignal = pyqtSignal(object)
    failed: QtCore.pyqtSignal = pyqtSignal()

    def __init__(
        self,
        cover_label: QLabel,
        size: ty.Tuple[int, int],
        book: Book,
    ):
        """
        :param cover_label: Экземпляр QLabel, для которого скачивается обложка.
        :param size: Размеры QLabel.
        :param book: Экземпляр книги.
        """
        super(DownloadPreviewWorker, self).__init__()
        self.cover_label, self.size, self.book = cover_label, size, book
        self.finished.connect(lambda pixmap: self.finish(pixmap))
        self.failed.connect(self.fail)

    def run(self):
        if not self.book.preview:  # Если у книги нет обложки
            self.failed.emit()
            return

        try:
            pixmap = Cache.get(self.book.preview)  # Проверяем кэш
            if not pixmap:
                # Скачивание
                context = ssl.SSLContext()
                data = urllib.request.urlopen(self.book.preview, context=context).read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                Cache.set(self.book.preview, pixmap)  # Заносим в кэш
            self.finished.emit(pixmap)
        except Exception:
            self.failed.emit()

    def finish(self, pixmap: QPixmap) -> None:
        self.cover_label.download_cover_thread.quit()
        self.cover_label.setMovie(None)  # Отключаем анимацию загрузки
        if os.path.isdir(self.book.dir_path):  # Если книга скачана
            # Сохраняем обложку
            pixmap.save(os.path.join(self.book.dir_path, "cover.jpg"), "jpeg")
        # Подстраиваем размер обложки под QLabel
        pixmap = pixmap.scaled(*self.size, Qt.KeepAspectRatio)
        self.cover_label.setPixmap(pixmap)

    def fail(self) -> None:
        self.cover_label.download_cover_thread.quit()
        self.cover_label.setMovie(None)  # Отключаем анимацию загрузки
        self.cover_label.hide()  # Скрываем элемент


def loadPreview(cover_label: QLabel, size: ty.Tuple[int, int], book: Book) -> None:
    """
    Устанавливает обложку книги в определенный QLabel.
    Если обложка не скачана - скачивает.
    :param cover_label: Экземпляр QLabel, для которого скачивается обложка.
    :param size: Размеры QLabel.
    :param book: Экземпляр книги.
    """
    cover_label.show()
    cover_path = os.path.join(book.dir_path, "cover.jpg")
    if os.path.isfile(cover_path):  # Если обложка скачана
        pixmap = QPixmap()
        pixmap.load(cover_path)
        pixmap = pixmap.scaled(*size, Qt.KeepAspectRatio)
        cover_label.setPixmap(pixmap)
    else:
        # Анимация загрузки
        cover_label.loading_cover_movie = QMovie(":/other/loading.gif")
        cover_label.loading_cover_movie.setScaledSize(QSize(50, 50))
        cover_label.setMovie(cover_label.loading_cover_movie)
        cover_label.loading_cover_movie.start()
        # Создаем и запускаем новый поток
        cover_label.download_cover_thread = QThread()
        cover_label.download_cover_worker = DownloadPreviewWorker(
            cover_label, size, book
        )
        cover_label.download_cover_worker.moveToThread(
            cover_label.download_cover_thread
        )
        cover_label.download_cover_thread.started.connect(
            cover_label.download_cover_worker.run
        )
        cover_label.download_cover_thread.start()


class DownloadBookWorker(QObject):
    """
    Реализует скачивание книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal()
    failed: QtCore.pyqtSignal = pyqtSignal(str)
    close: QtCore.pyqtSignal = pyqtSignal()

    def __init__(self, main_window: MainWindow, book: Book):
        super(DownloadBookWorker, self).__init__()
        self.main_window, self.book = main_window, book
        self.drv = [drv for drv in drivers if self.book.url.startswith(drv().site_url)][
            0
        ]()  # Драйвер, который нужно использовать для скачивания
        self.finished.connect(self.finish)
        self.failed.connect(lambda text: self.fail(text))
        self.close.connect(self._close)

    def run(self):
        try:
            self.drv.download_book(self.book, DownloadProcessHandler(self.main_window))
            books = Books(os.environ["DB_PATH"])
            books.insert(**vars(self.book))  # Добавляем книгу в бд
            self.finished.emit()
        except Exception as err:
            # TODO: Необходимо реализовать нормальный обзор ошибок
            self.failed.emit(str(err))
        finally:
            self.main_window.downloadable_book = ...

    def finish(self):
        self.main_window.download_book_thread.quit()
        # Если пользователь находится на странице скачиваемой книги
        if self.main_window.pbFrame.minimumWidth() == 0:
            self.main_window.openBookPage(self.book)  # Обновляем страницу
        else:
            # Закрываем полосу прогресса
            self.main_window.pb_animation = QPropertyAnimation(
                self.main_window.pbFrame, b"minimumWidth"
            )
            self.main_window.pb_animation.setDuration(150)
            self.main_window.pb_animation.setStartValue(150)
            self.main_window.pb_animation.setEndValue(0)
            self.main_window.pb_animation.setEasingCurve(QEasingCurve.InOutQuart)
            self.main_window.pb_animation.start()
            if (
                self.main_window.stackedWidget.currentWidget()
                == self.main_window.libraryPage
            ):
                self.main_window.openLibraryPage()

    def fail(self, text: str):
        self.main_window.download_book_thread.quit()
        self.main_window.openInfoPage(
            text=text,
            btn_text="Вернуться в библиотеку",
            btn_function=lambda: self.main_window.stackedWidget.setCurrentWidget(
                self.main_window.libraryPage
            ),
        )

    def _close(self):
        file = self.drv.__dict__.get("_file")
        if file:
            file.close()


class DownloadProcessHandler(BaseDownloadProcessHandler):
    def __init__(self, main_window: MainWindow):
        """
        :param main_window: Экземпляр главного окна.
        """
        super(DownloadProcessHandler, self).__init__()
        self.main_window = main_window
        self._last_size = ""

    def show_progress(self) -> None:
        """
        Отображение прогресса.
        """
        progress = int(round(self.done_size / (self.total_size / 100), 0))
        self.main_window.downloadingProgressBarLg.setValue(progress)
        self.main_window.downloadingProgressBar.setValue(progress)
        self.main_window.downloadingProgressBar.setToolTip(
            f"{convert_into_bits(self.done_size)} / {convert_into_bits(self.total_size)}",
        )


def prepareProgressBar(pb: QProgressBar) -> None:
    """
    Подготовка полосы загрузки.
    :param pb: Экземпляр QProgressBar.
    """

    class ToolTipUpdater(QObject):
        """
        Реализует динамическое изменение всплывающей подсказки.
        """

        def timerEvent(self, x) -> None:
            QToolTip.showText(pb.toolTipPos, pb.toolTip(), pb)

    def eventFilter(event: QEvent) -> bool:
        """
        Обработчик событий полосы загрузки.
        :param event:
        """
        if event.type() == QEvent.ToolTip:  # Удержание курсора на объекте
            pb.toolTipPos = event.globalPos()  # Позиция, гду будет отображена подсказка
            pb.toolTipUpdater = ToolTipUpdater()
            pb.toolTipTimer = QBasicTimer()
            pb.toolTipTimer.start(100, pb.toolTipUpdater)  # Обновление подсказки
            return True
        elif event.type() == QEvent.Leave:  # Курсор покидает объект
            if pb.__dict__.get("toolTipPos"):
                pb.toolTipTimer.stop()
                pb.toolTipPos = None
                QToolTip.hideText()  # Скрываем подсказку
        return QProgressBar.event(pb, event)

    pb.toolTipPos = None
    pb.event = eventFilter


def downloadBook(main_window: MainWindow, book: Book) -> None:
    """
    Запускает скачивание книги.
    :param main_window: Экземпляр главного окна.
    :param book: Экземпляр книги.
    """
    if main_window.downloadable_book is not ...:
        QMessageBox.information(
            main_window,
            "Предупреждение",
            "Дождитесь окончания скачивания другой книги",
        )
        return

    main_window.downloadingProgressBarLg.setValue(0)
    main_window.downloadingProgressBar.setValue(0)

    main_window.playerContent.setCurrentWidget(main_window.downloadingPage)
    main_window.saveBtn.hide()
    main_window.downloadable_book = book

    # Создаем и запускаем новый поток
    main_window.download_book_thread = QThread()
    main_window.download_book_worker = DownloadBookWorker(main_window, book)
    main_window.download_book_worker.moveToThread(main_window.download_book_thread)
    main_window.download_book_thread.started.connect(
        main_window.download_book_worker.run
    )
    main_window.download_book_thread.start()


class DeleteBookWorker(QObject):
    """
    Реализует удаление книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal()
    failed: QtCore.pyqtSignal = pyqtSignal(str)

    def __init__(self, main_window: MainWindow, book: ty.Union[Book, Books]):
        super(DeleteBookWorker, self).__init__()
        self.main_window, self.book = main_window, book
        self.finished.connect(self.finish)
        self.failed.connect(lambda text: self.fail(text))

    def run(self):
        try:
            self.main_window.btnGroupFrame.setDisabled(True)
            self.main_window.btnGroupFrame_2.setDisabled(True)
            # Удаление книги из бд
            if self.book.__dict__.get("id"):
                books = Books(os.environ["DB_PATH"])
                books.api.execute("""DELETE FROM books WHERE id=?""", self.book.id)
                books.api.commit()
            # Удаление файлов книги
            if os.path.isdir(self.book.dir_path):
                for root, dirs, files in os.walk(self.book.dir_path):
                    for file in files:
                        os.remove(os.path.join(root, file))
                    os.rmdir(root)
            self.finished.emit()
        except Exception as err:
            # TODO: Необходимо реализовать нормальный обзор ошибок
            self.failed.emit(str(err))
        finally:
            self.main_window.btnGroupFrame.setDisabled(False)
            self.main_window.btnGroupFrame_2.setDisabled(False)

    def finish(self):
        self.main_window.delete_book_thread.quit()
        self.main_window.openLibraryPage()

    def fail(self, text: str):
        self.main_window.delete_book_thread.quit()
        self.main_window.openInfoPage(
            text=text,
            btn_text="Вернуться в библиотеку",
            btn_function=lambda: self.main_window.stackedWidget.setCurrentWidget(
                self.main_window.libraryPage
            ),
        )


def stopBookDownloading(main_window: MainWindow) -> None:
    """
    Останавливает загрузку книги и запускает процесс её удаления.
    :param main_window: Экземпляр главного окна.
    """
    answer = QMessageBox.question(
        main_window,
        "Подтвердите действие",
        "Вы действительно хотите прервать скачивание книги?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )

    if answer == QMessageBox.No:
        return

    # Останавливаем скачивание
    main_window.download_book_worker.close.emit()
    main_window.download_book_thread.terminate()

    downloadable_book = main_window.downloadable_book
    main_window.downloadable_book = ...

    # Открываем страницу загрузки
    main_window.delete_book_loading_movie = QMovie(":/other/loading.gif")
    main_window.delete_book_loading_movie.setScaledSize(QSize(50, 50))
    main_window.openInfoPage(movie=main_window.delete_book_loading_movie)

    # Создаем и запускаем новый поток
    main_window.delete_book_thread = QThread()
    main_window.delete_book_worker = DeleteBookWorker(main_window, downloadable_book)
    main_window.delete_book_worker.moveToThread(main_window.delete_book_thread)
    main_window.delete_book_thread.started.connect(main_window.delete_book_worker.run)
    main_window.delete_book_thread.start()


def deleteBook(main_window: MainWindow, book: Books = None) -> None:
    """
    Запускает удаление книги.
    :param main_window: Экземпляр главного окна.
    :param book: Экземпляр книги. (Если не передан используется main_window.book)
    :return:
    """
    book = book or main_window.book
    if book is ...:
        return

    answer = QMessageBox.question(
        main_window,
        "Подтвердите действие",
        "Вы действительно хотите удалить книгу из библиотеки?",
        QMessageBox.Yes | QMessageBox.No,
        QMessageBox.No,
    )

    if answer == QMessageBox.No:
        return

    # Открываем страницу загрузки
    main_window.delete_book_loading_movie = QMovie(":/other/loading.gif")
    main_window.delete_book_loading_movie.setScaledSize(QSize(50, 50))
    main_window.openInfoPage(movie=main_window.delete_book_loading_movie)

    # Создаем и запускаем новый поток
    main_window.delete_book_thread = QThread()
    main_window.delete_book_worker = DeleteBookWorker(main_window, book)
    main_window.delete_book_worker.moveToThread(main_window.delete_book_thread)
    main_window.delete_book_thread.started.connect(main_window.delete_book_worker.run)
    main_window.delete_book_thread.start()


def toggleFavorite(main_window: MainWindow, book: Books = None) -> None:
    book = book or main_window.book
    book.favorite = not book.favorite
    icon = QIcon()
    if book.favorite:
        icon.addPixmap(
            QPixmap(":/other/star_fill.svg"),
            QIcon.Normal,
            QIcon.Off,
        )
    else:
        icon.addPixmap(QPixmap(":/other/star.svg"), QIcon.Normal, QIcon.Off)
    main_window.sender().setIcon(icon)
    book.save()

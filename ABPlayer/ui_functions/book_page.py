from __future__ import annotations

import os
import ssl
import typing as ty
import urllib.request

from PyQt5.QtCore import (
    Qt,
    QSize,
    QThread,
    QObject,
    pyqtSignal,
    QEasingCurve,
    QPropertyAnimation,
)
from PyQt5.QtGui import QMovie, QPixmap
from PyQt5.QtWidgets import QMessageBox

from database import Books
from drivers import drivers, BaseDownloadProcessHandler

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from PyQt5.QtWidgets import QLabel
    from main_window import MainWindow
    from database import Book


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


def load_preview(cover_label: QLabel, size: ty.Tuple[int, int], book: Book) -> None:
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

    def __init__(self, main_window: MainWindow, book: Book):
        super(DownloadBookWorker, self).__init__()
        self.main_window, self.book = main_window, book
        self.finished.connect(self.finish)
        self.failed.connect(lambda text: self.fail(text))

    def run(self):
        try:
            drv = [drv for drv in drivers if self.book.url.startswith(drv().site_url)][
                0
            ]()  # Драйвер, который нужно использовать для скачивания
            drv.download_book(self.book, DownloadProcessHandler(self.main_window))
            books = Books(os.environ["DB_PATH"])
            books.insert(**vars(self.book))  # Добавляем книгу в бд
            self.finished.emit()
        except Exception as err:
            # TODO: Необходимо реализовать нормальный обзор ошибок
            self.failed.emit(str(err))

    def finish(self):
        self.main_window.downloading = False
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

    def fail(self, text: str):
        self.main_window.downloading = False
        self.main_window.download_book_thread.quit()
        self.main_window.openInfoPage(
            text=text,
            btn_text="Вернуться в библиотеку",
            btn_function=lambda: self.main_window.stackedWidget.setCurrentWidget(
                self.main_window.libraryPage
            ),
        )


class DownloadProcessHandler(BaseDownloadProcessHandler):
    def __init__(self, main_window: MainWindow):
        """
        :param main_window: Экземпляр главного окна.
        """
        super(DownloadProcessHandler, self).__init__()
        self.main_window = main_window

    def show_progress(self) -> None:
        """
        Отображение прогресса.
        """
        progress = int(round(self.done_size / (self.total_size / 100), 0))
        self.main_window.downloadingProgressBarLg.setValue(progress)


def download_book(main_window: MainWindow, book: Book) -> None:
    """
    Запускает скачивание книги.
    :param main_window: Экземпляр главного окна.
    :param book: Экземпляр книги.
    """
    if main_window.downloading:
        # TODO: Нужно показывать диалоговое окно
        return

    main_window.downloadingProgressBarLg.setValue(0)
    main_window.downloadingProgressBar.setValue(0)

    main_window.playerContent.setCurrentWidget(main_window.downloadingPage)
    main_window.saveBtn.hide()
    main_window.downloading = True

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

    def __init__(self, main_window: MainWindow):
        super(DeleteBookWorker, self).__init__()
        self.main_window = main_window
        self.finished.connect(self.finish)
        self.failed.connect(lambda text: self.fail(text))

    def run(self):
        try:
            self.main_window.btnGroupFrame.setDisabled(True)
            self.main_window.btnGroupFrame_2.setDisabled(True)
            books = Books(os.environ["DB_PATH"])
            books.api.execute(
                """DELETE FROM books WHERE id=?""", self.main_window.book.id
            )
            books.api.commit()
            for root, dirs, files in os.walk(self.main_window.book.dir_path):
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


def delete_book(main_window: MainWindow) -> None:
    if main_window.book is ...:
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
    main_window.delete_book_worker = DeleteBookWorker(main_window)
    main_window.delete_book_worker.moveToThread(main_window.delete_book_thread)
    main_window.delete_book_thread.started.connect(main_window.delete_book_worker.run)
    main_window.delete_book_thread.start()

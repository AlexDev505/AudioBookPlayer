from __future__ import annotations

import typing as ty
import urllib.request
import ssl
import os

from PyQt5.QtCore import (
    QSize,
    QThread,
    QObject,
    pyqtSignal,
    Qt,
    QEasingCurve,
    QPropertyAnimation,
)
from PyQt5.QtGui import QMovie, QPixmap

from drivers import drivers, DownloadProcessHandler
from database import Books

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from PyQt5.QtWidgets import QLabel
    from main_window import MainWindow
    from database import Book


class Cache(object):
    cache = {}

    @classmethod
    def get(cls, item: str):
        return cls.cache.get(item)

    @classmethod
    def set(cls, key: str, value: QPixmap):
        if len(cls.cache) >= 4:
            del cls.cache[list(cls.cache.keys())[0]]
        cls.cache[key] = value


class DownloadPreviewWorker(QObject):
    finished: QtCore.pyqtSignal = pyqtSignal(object)
    failed: QtCore.pyqtSignal = pyqtSignal()

    def __init__(
        self,
        main_window: ty.Any,
        cover_label: QLabel,
        size: ty.Tuple[int, int],
        book: Book,
    ):
        super(DownloadPreviewWorker, self).__init__()
        self.main_window = main_window
        self.cover_label = cover_label
        self.size = size
        self.book = book
        self.finished.connect(lambda pixmap: self.finish(pixmap))
        self.failed.connect(self.fail)

    def run(self):
        if not self.book.preview:
            self.failed.emit()
            return

        try:
            pixmap = Cache.get(self.book.preview)
            if not pixmap:
                context = ssl.SSLContext()
                data = urllib.request.urlopen(self.book.preview, context=context).read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                Cache.set(self.book.preview, pixmap)
            self.finished.emit(pixmap)
        except Exception:
            self.failed.emit()

    def finish(self, pixmap: QPixmap):
        self.main_window.download_cover_thread.quit()
        self.cover_label.setMovie(None)
        if os.path.isdir(self.book.dir_path):
            pixmap.save(os.path.join(self.book.dir_path, "cover.jpg"), "jpeg")
        pixmap = pixmap.scaled(*self.size, Qt.KeepAspectRatio)
        self.cover_label.setPixmap(pixmap)

    def fail(self):
        self.main_window.download_cover_thread.quit()
        self.cover_label.hide()


def download_preview(
    main_window: ty.Any, cover_label: QLabel, size: ty.Tuple[int, int], book: Book
) -> None:
    cover_label.show()
    main_window.loading_cover_movie = QMovie(":/other/loading.gif")
    main_window.loading_cover_movie.setScaledSize(QSize(50, 50))
    cover_label.setMovie(main_window.loading_cover_movie)
    main_window.loading_cover_movie.start()
    main_window.download_cover_thread = QThread()
    main_window.download_cover_worker = DownloadPreviewWorker(
        main_window, cover_label, size, book
    )
    main_window.download_cover_worker.moveToThread(main_window.download_cover_thread)
    main_window.download_cover_thread.started.connect(
        main_window.download_cover_worker.run
    )
    main_window.download_cover_thread.start()


class DownloadBookWorker(QObject):
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
            ]()
            drv.download_book(self.book, DownloadBookProcessHandler(self.main_window))
            books = Books(os.environ["DB_PATH"])
            books.insert(**vars(self.book))
            self.finished.emit()
        except Exception as err:
            self.failed.emit(str(err))

    def finish(self):
        self.main_window.downloading = False
        self.main_window.download_book_thread.quit()
        if self.main_window.pbFrame.minimumWidth() == 0:
            self.main_window.openBookPage(self.book)
        else:
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


class DownloadBookProcessHandler(DownloadProcessHandler):
    def __init__(self, main_window: MainWindow):
        super(DownloadBookProcessHandler, self).__init__()
        self.main_window = main_window

    def move_progress(self):
        progress = int(round(self.done_size / (self.total_size / 100), 0))
        self.main_window.downloadingProgressBarLg.setValue(progress)


def download_book(main_window: MainWindow, book: Book) -> None:
    main_window.downloadingProgressBarLg.setValue(0)
    main_window.downloadingProgressBar.setValue(0)
    main_window.playerContent.setCurrentWidget(main_window.downloadingPage)
    main_window.saveBtn.hide()

    main_window.downloading = True
    main_window.download_book_thread = QThread()
    main_window.download_book_worker = DownloadBookWorker(main_window, book)
    main_window.download_book_worker.moveToThread(main_window.download_book_thread)
    main_window.download_book_thread.started.connect(
        main_window.download_book_worker.run
    )
    main_window.download_book_thread.start()

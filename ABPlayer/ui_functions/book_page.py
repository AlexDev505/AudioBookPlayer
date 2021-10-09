from __future__ import annotations

import typing as ty
import urllib.request
import ssl

from PyQt5.QtCore import QSize, QThread, QObject, pyqtSignal, Qt
from PyQt5.QtGui import QMovie, QPixmap

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
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


class DownloadWorker(QObject):
    finished: QtCore.pyqtSignal = pyqtSignal(object)
    failed: QtCore.pyqtSignal = pyqtSignal()

    def __init__(self, main_window: MainWindow, book: Book):
        super(DownloadWorker, self).__init__()
        self.main_window, self.book = main_window, book
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
                pixmap = pixmap.scaled(230, 230, Qt.KeepAspectRatio)
                Cache.set(self.book.preview, pixmap)
            self.finished.emit(pixmap)
        except Exception:
            self.failed.emit()

    def finish(self, pixmap: QPixmap):
        self.main_window.download_cover_thread.quit()
        self.main_window.bookCoverLg.setMovie(None)
        self.main_window.bookCoverLg.setPixmap(pixmap)

    def fail(self):
        self.main_window.download_cover_thread.quit()
        self.main_window.bookCoverLg.hide()


def download_preview(main_window: MainWindow, book: Book) -> None:
    main_window.bookCoverLg.show()
    main_window.loading_cover_movie = QMovie(":/other/loading.gif")
    main_window.loading_cover_movie.setScaledSize(QSize(50, 50))
    main_window.bookCoverLg.setMovie(main_window.loading_cover_movie)
    main_window.loading_cover_movie.start()
    main_window.download_cover_thread = QThread()
    main_window.download_cover_worker = DownloadWorker(main_window, book)
    main_window.download_cover_worker.moveToThread(main_window.download_cover_thread)
    main_window.download_cover_thread.started.connect(
        main_window.download_cover_worker.run
    )
    main_window.download_cover_thread.start()

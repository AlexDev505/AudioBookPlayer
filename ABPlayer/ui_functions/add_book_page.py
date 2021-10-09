from __future__ import annotations

import typing as ty
import webbrowser

from PyQt5.QtCore import QSize, QThread, QObject, pyqtSignal
from PyQt5.QtGui import QMovie

from drivers import drivers

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow
    from drivers import Driver
    from database import Book


class SearchWorker(QObject):
    finished: QtCore.pyqtSignal = pyqtSignal(object)
    failed: QtCore.pyqtSignal = pyqtSignal()

    def __init__(self, main_window: MainWindow, drv: Driver, url: str):
        super(SearchWorker, self).__init__()
        self.main_window, self.drv, self.url = main_window, drv, url
        self.finished.connect(lambda book: self.finish(book))
        self.failed.connect(self.fail)

    def run(self) -> None:
        try:
            book = self.drv.get_book(self.url)
            self.finished.emit(book)
        except Exception:
            self.failed.emit()

    def finish(self, book: Book):
        self.main_window.search_thread.quit()
        self.main_window.openBookPage(book)

    def fail(self):
        self.main_window.search_thread.quit()
        self.main_window.openInfoPage(
            text="Не удалось получить данные об этой книге",
            btn_text="Открыть ссылку в браузере",
            btn_function=lambda: webbrowser.open_new_tab(self.url),
        )


def search(main_window: MainWindow) -> None:
    url = main_window.searchNewBookLineEdit.text().strip()
    main_window.searchNewBookLineEdit.clear()
    if not url:
        main_window.searchNewBookLineEdit.setFocus()
        return
    else:
        url = url.strip()

    main_window.openInfoPage(movie=_loading_animation(main_window))

    if not any(url.startswith(drv().site_url) for drv in drivers):
        main_window.openInfoPage(
            text="Драйвер для данного сайта не найден",
            btn_text="Вернуться",
            btn_function=lambda: main_window.stackedWidget.setCurrentWidget(
                main_window.addBookPage
            ),
        )
        return

    drv = [drv for drv in drivers if url.startswith(drv().site_url)][0]()

    main_window.search_thread = QThread()
    main_window.search_worker = SearchWorker(main_window, drv, url)
    main_window.search_worker.moveToThread(main_window.search_thread)
    main_window.search_thread.started.connect(main_window.search_worker.run)
    main_window.search_thread.start()


def _loading_animation(main_window: MainWindow) -> QMovie:
    main_window.movie = QMovie(":/other/loading.gif")
    main_window.movie.setScaledSize(QSize(50, 50))
    return main_window.movie

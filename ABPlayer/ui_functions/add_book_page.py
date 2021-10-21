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
    """
    Класс реализующий поиск книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal(object)  # Поиск завершен
    failed: QtCore.pyqtSignal = pyqtSignal()  # Ошибка при поиске

    def __init__(self, main_window: MainWindow, drv: Driver, url: str):
        super(SearchWorker, self).__init__()
        self.main_window, self.drv, self.url = main_window, drv, url
        self.finished.connect(lambda book: self.finish(book))
        self.failed.connect(self.fail)

    def run(self) -> None:
        self.main_window.setLock(True)
        try:
            book = self.drv.get_book(self.url)
            self.finished.emit(book)
        except Exception:
            self.failed.emit()
        self.main_window.setLock(False)

    def finish(self, book: Book) -> None:
        self.main_window.search_thread.quit()
        self.main_window.openBookPage(book)

    def fail(self) -> None:
        self.main_window.search_thread.quit()
        self.main_window.openInfoPage(
            text="Не удалось получить данные об этой книге",
            btn_text="Открыть ссылку в браузере",
            btn_function=lambda: webbrowser.open_new_tab(self.url),
        )


def search(main_window: MainWindow) -> None:
    """
    Запускает поиск книги.
    :param main_window: Экземпляр главного окна.
    """
    url = main_window.searchNewBookLineEdit.text().strip()
    main_window.searchNewBookLineEdit.clear()  # Очищаем поле ввода
    if not url:  # Поле ввода пустое
        main_window.searchNewBookLineEdit.setFocus()
        return
    url = url.strip()

    # Открываем страницу загрузки
    main_window.search_loading_movie = QMovie(":/other/loading.gif")
    main_window.search_loading_movie.setScaledSize(QSize(50, 50))
    main_window.openInfoPage(movie=main_window.search_loading_movie)

    # Драйвер не найден
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

    # Создаём и запускаем новый поток
    main_window.search_thread = QThread()
    main_window.search_worker = SearchWorker(main_window, drv, url)
    main_window.search_worker.moveToThread(main_window.search_thread)
    main_window.search_thread.started.connect(main_window.search_worker.run)
    main_window.search_thread.start()

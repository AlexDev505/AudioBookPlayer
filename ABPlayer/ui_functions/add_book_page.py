"""

Функционал страницы добавления новой книги.

"""

from __future__ import annotations

import typing as ty
import webbrowser

from PyQt5.QtCore import pyqtSignal

from drivers import drivers
from tools import BaseWorker

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow
    from drivers.base import Driver
    from database.tables.books import Book


class SearchWorker(BaseWorker):
    """
    Класс реализующий поиск книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal(object)  # Поиск завершен
    failed: QtCore.pyqtSignal = pyqtSignal(str)  # Ошибка при поиске

    def __init__(self, main_window: MainWindow, drv: Driver, url: str):
        super(SearchWorker, self).__init__()
        self.main_window, self.drv, self.url = main_window, drv, url

    def connectSignals(self) -> None:
        self.finished.connect(lambda book: self.finish(book))
        self.failed.connect(lambda message: self.fail(message))

    def worker(self) -> None:
        self.main_window.setLock(True)
        try:
            book = self.drv.get_book(self.url)
            self.finished.emit(book)
        except Exception as err:
            if "ERR_INTERNET_DISCONNECTED" in str(err):
                self.failed.emit(
                    "Не удалось подключиться к серверу.\n"
                    "Проверьте интернет соединение."
                )
            else:
                self.failed.emit(
                    "Не удалось получить данные об этой книге.\n"
                    "Проверьте правильность введенной ссылки."
                )
        self.main_window.setLock(False)

    def finish(self, book: Book) -> None:
        self.main_window.openBookPage(book)

    def fail(self, message: str) -> None:
        self.main_window.openInfoPage(
            text=message,
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

    main_window.openLoadingPage()

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
    main_window.searchWorker = SearchWorker(main_window, drv, url)
    main_window.searchWorker.start()

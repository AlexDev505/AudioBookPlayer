"""

Функционал панели фильтрации.

"""

from __future__ import annotations

import difflib
import os
import typing as ty

from PyQt5.QtCore import QTimer, pyqtSignal
from PyQt5.QtGui import QIcon
from loguru import logger

from database import Books
from tools import BaseWorker, pretty_view

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow


def resetAuthor(main_window: MainWindow) -> None:
    """
    Сбрасывает фильтрацию по автору.
    :param main_window: Экземпляр главного окна.
    """
    main_window.sortAuthor.setCurrentIndex(0)
    logger.debug("Sorting by author has been reset")


def resetseries(main_window: MainWindow) -> None:
    """
    Сбрасывает фильтрацию по циклу.
    :param main_window: Экземпляр главного окна.
    """
    main_window.sortSeries.setCurrentIndex(0)
    logger.debug("Sorting by series has been reset")


def toggleInvertSort(main_window: MainWindow) -> None:
    """
    Обрабатывает нажатие на кнопку инверсии сортировки.
    Изменяет иконку кнопки.
    :param main_window: Экземпляр главного окна.
    """
    icon = QIcon(
        ":/other/sort_up.svg"
        if main_window.invertSortBtn.isChecked()
        else ":/other/sort_down.svg"
    )
    main_window.invertSortBtn.setIcon(icon)
    main_window.openLibraryPage()
    logger.opt(colors=True).debug(
        f"Invert sorting: <y>{main_window.invertSortBtn.isChecked()}</y>"
    )


class KeywordSearchWorker(BaseWorker):
    """
    Класс реализующий поиск книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal(object)  # Поиск завершен
    failed: QtCore.pyqtSignal = pyqtSignal()  # Ошибка при поиске

    def __init__(self, main_window: MainWindow, text: str):
        super(KeywordSearchWorker, self).__init__()
        self.main_window, self.text = main_window, text

    def connectSignals(self) -> None:
        self.finished.connect(lambda books: self.finish(books))
        self.failed.connect(self.fail)

    @logger.catch
    def worker(self) -> None:
        logger.debug("Starting the keyword search process")
        self.main_window.setLock(True)
        try:
            books = Books(os.environ["DB_PATH"]).filter(return_list=True)
            if not len(books):
                raise ValueError
            # Отключаем объекты от бд, чтобы не возникло ошибок из-за потоков
            for book in books:
                del book.__dict__["_Table__api"]
            search_array = {
                book.id: book.name.lower().split() + book.author.lower().split()
                for book in books
            }  # Данные о книгах
            logger.opt(colors=True).debug("search_array: " + pretty_view(search_array))
            search_words = self.text.lower().split()  # Слова по которым будем искать
            logger.opt(colors=True).debug("search_words: " + pretty_view(search_words))
            matched_books_ids = []  # Идентификаторы найденных книг
            # Поиск
            for i, array in search_array.items():
                for search_word in search_words:
                    if difflib.get_close_matches(search_word, array):
                        matched_books_ids.append(i)
                        break
            logger.opt(colors=True).debug(
                "matched_books_ids: " + pretty_view(matched_books_ids)
            )
            self.finished.emit(matched_books_ids)
        except Exception as err:
            self.failed.emit()
            raise err
        self.main_window.setLock(False)

    def finish(self, books_ids: ty.List[int]) -> None:
        # На маленьких объемах поиск работает слишком быстро,
        # поэтому добавляем небольшую задержку
        # для избежания ошибки при быстром переключении страниц
        QTimer.singleShot(100, lambda: self.main_window.openLibraryPage(books_ids))

    def fail(self) -> None:
        QTimer.singleShot(100, lambda: self.main_window.openLibraryPage([]))


def search(main_window: MainWindow) -> None:
    """
    Запускает поиск книг по ключевым словам.
    :param main_window: Экземпляр главного окна.
    """
    text = main_window.searchBookLineEdit.text().strip()
    if not text:
        main_window.search_on = False
        main_window.openLibraryPage()
        return

    main_window.search_on = True

    main_window.openLoadingPage()

    # Создаём и запускаем новый поток
    main_window.SearchWorker = KeywordSearchWorker(main_window, text)
    main_window.SearchWorker.start()

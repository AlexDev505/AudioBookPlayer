from __future__ import annotations

import difflib
import os
import typing as ty

from PyQt5.QtCore import QThread, QObject, pyqtSignal, QSize, QTimer
from PyQt5.QtGui import QIcon, QPixmap, QMovie

from database import Books

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow


def resetAuthor(main_window: MainWindow) -> None:
    """
    Сбрасывает фильтрацию по автору.
    :param main_window: Экземпляр главного окна.
    """
    main_window.sortAuthor.setCurrentIndex(0)


def toggleInvertSort(main_window: MainWindow) -> None:
    """
    Обрабатывает нажатие на кнопку инверсии сортировки.
    Изменяет иконку кнопки.
    :param main_window: Экземпляр главного окна.
    """
    icon = QIcon()
    if main_window.invertSortBtn.isChecked():
        icon.addPixmap(QPixmap(":/other/sort_up.svg"), QIcon.Normal, QIcon.Off)
    else:
        icon.addPixmap(QPixmap(":/other/sort_down.svg"), QIcon.Normal, QIcon.Off)
    main_window.invertSortBtn.setIcon(icon)
    main_window.openLibraryPage()


class SearchWorker(QObject):
    """
    Класс реализующий поиск книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal(object)  # Поиск завершен
    failed: QtCore.pyqtSignal = pyqtSignal()  # Ошибка при поиске

    def __init__(self, main_window: MainWindow, text: str):
        super(SearchWorker, self).__init__()
        self.main_window, self.text = main_window, text
        self.finished.connect(lambda books: self.finish(books))
        self.failed.connect(self.fail)

    def run(self) -> None:
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
            search_words = self.text.lower().split()  # Слова по которым будем искать
            matched_books_ids = []  # Идентификаторы найденных книг
            # Поиск
            for i, array in search_array.items():
                for search_word in search_words:
                    if difflib.get_close_matches(search_word, array):
                        matched_books_ids.append(i)
                        break
            self.finished.emit(matched_books_ids)
        except Exception:
            self.failed.emit()
        self.main_window.setLock(False)

    def finish(self, books_ids: ty.List[int]) -> None:
        self.main_window.search_thread.quit()
        QTimer.singleShot(100, lambda: self.main_window.openLibraryPage(books_ids))

    def fail(self) -> None:
        self.main_window.search_thread.quit()
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

    # Открываем страницу загрузки
    main_window.search_loading_movie = QMovie(":/other/loading.gif")
    main_window.search_loading_movie.setScaledSize(QSize(50, 50))
    main_window.openInfoPage(movie=main_window.search_loading_movie)

    # Создаём и запускаем новый поток
    main_window.search_thread = QThread()
    main_window.search_worker = SearchWorker(main_window, text)
    main_window.search_worker.moveToThread(main_window.search_thread)
    main_window.search_thread.started.connect(main_window.search_worker.run)
    main_window.search_thread.start()

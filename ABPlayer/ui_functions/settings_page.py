"""

Функционал страницы настроек.

"""

from __future__ import annotations

import os
import pathlib
import shutil
import typing as ty
from contextlib import suppress

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QFileDialog, QMessageBox
from loguru import logger

import styles
from database import Config, Books
from tools import BaseWorker

if ty.TYPE_CHECKING:
    from main_window import MainWindow
    from PyQt5 import QtCore


class SearchWorker(BaseWorker):
    """
    Класс реализующий поиск книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal()  # Перенос завершен

    def __init__(self, main_window: MainWindow, new_path: str):
        super(SearchWorker, self).__init__()
        self.main_window, self.new_path = main_window, new_path

    def connectSignals(self) -> None:
        self.finished.connect(lambda: self.finish())

    def worker(self) -> None:
        logger.opt(colors=True).debug("Starting moving library.")
        self.main_window.setLock(True)

        books: dict[str, list[str]] = {}
        for root, _, files in os.walk(os.environ["books_folder"]):
            if ".abp" in files:
                books[root.split(os.environ["books_folder"])[1][1:]] = [
                    file
                    for file in files
                    if file.endswith(".mp3") or file in {"cover.jpg", ".abp"}
                ]

        logger.opt(colors=True).debug(f"{len(books)} books found")

        # Копируем книги в новую директорию
        for book_dir_name, files in books.items():
            old_book_path = os.path.join(os.environ["books_folder"], book_dir_name)
            new_book_path = pathlib.Path(self.new_path, book_dir_name)
            logger.opt(colors=True).debug(
                f"Copying <y>{old_book_path}</y> to <y>{new_book_path}</y>"
            )
            new_book_path.mkdir(parents=True, exist_ok=True)  # Создаем директорию книги
            for file_name in files:
                old_file_path = os.path.join(old_book_path, file_name)
                new_file_path = os.path.join(new_book_path, file_name)
                logger.opt(colors=True).trace(
                    f"Copying <y>{old_file_path}</y> to <y>{new_file_path}</y>"
                )
                shutil.copyfile(old_file_path, new_file_path)  # Копируем
                try:  # Пробуем удалить старый файл
                    os.remove(old_file_path)
                except Exception:
                    logger.opt(colors=True).error(
                        f"Unable to delete file <y>{old_file_path}</y>."
                    )

            logger.opt(colors=True).trace(
                f"Copying <y>{old_book_path}</y> to <y>{new_book_path}</y> complete"
            )

            with suppress(Exception):  # Пробуем удалить старую директорию книги
                os.rmdir(old_book_path)

                book_dir_name = book_dir_name.replace("\\", "/")
                if book_dir_name.endswith("/"):
                    book_dir_name = book_dir_name[1:]

                while "/" in book_dir_name:
                    book_dir_name = book_dir_name[: book_dir_name.rfind("/")]
                    os.rmdir(os.path.join(os.environ["books_folder"], book_dir_name))

        old_books_folder = os.environ["books_folder"]
        Config.update(
            books_folder=self.new_path
        )  # Обновляем настройки в бд и виртуальном окружении
        logger.opt(colors=True).debug(
            "Directory with books changed. "
            f"<y>{old_books_folder}</y> -> <y>{os.environ['books_folder']}</y>"
        )

        logger.trace("Loading library")

        db = Books(os.environ["DB_PATH"])
        logger.trace("Dropping library table")
        db.api.execute("DROP TABLE IF EXISTS books")
        logger.trace("Creating library table")
        db.create_table()
        logger.trace("Library table created")

        abp_files: list[str] = []
        for root, _, files in os.walk(os.environ["books_folder"]):
            if ".abp" in files:
                abp_files.append(os.path.join(root, ".abp"))

        logger.debug(f"{len(abp_files)} abp files found")

        for abp in abp_files:
            logger.trace(f"Loading {abp}")
            book = Books.load_from_storage(abp)
            db.insert(**book)

        self.finished.emit()
        self.main_window.setLock(False)

    def finish(self) -> None:
        self.main_window.stackedWidget.setCurrentWidget(self.main_window.settingsPage)
        QMessageBox.information(
            self.main_window, "Информация", "Папка успешно изменена"
        )


@logger.catch
def setDirWithBooks(main_window: MainWindow) -> None:
    """
    Изменяет путь к директории с книгами.
    :param main_window: Экземпляр главного окна.
    """
    logger.debug("Changing the directory with books")
    if main_window.downloadable_book is not ...:
        logger.debug("Directory change canceled")
        QMessageBox.information(
            main_window, "Предупреждение", "Дождитесь окончания скачивания книги"
        )
        return
    # Открываем диалог с пользователем
    path = QFileDialog.getExistingDirectory(main_window, "Выберите папку")
    if path is None or not str(path).strip():
        logger.debug("Directory not selected")
        return
    logger.opt(colors=True).debug(f"Directory selected: <y>{path}</y>")

    main_window.openLoadingPage()  # Открываем страницу загрузки

    # Создаём и запускаем новый поток
    main_window.searchWorker = SearchWorker(main_window, path)
    main_window.searchWorker.start()


def openDirWithBooks() -> None:
    logger.trace("Opening a directory with books")
    try:
        os.startfile(os.environ["books_folder"])
    except FileNotFoundError:
        Config.init()
        os.startfile(os.environ["books_folder"])


def changeTheme(main_window: MainWindow) -> None:
    """
    Изменяет тему.
    :param main_window: Экземпляр главного окна.
    """
    old_theme = os.environ["theme"]
    main_window.centralwidget.setStyleSheet(
        styles.get_style_sheet(main_window.themeSelecror.currentText())
    )
    Config.update(theme=main_window.themeSelecror.currentText())
    logger.opt(colors=True).debug(
        f"Theme changed. <y>{old_theme}</y> -> <y>{os.environ['theme']}</y>"
    )

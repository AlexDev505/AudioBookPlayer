"""

Функционал страницы настроек.

"""

from __future__ import annotations

import os
import pathlib
import shutil
import typing as ty

from PyQt5.QtWidgets import QFileDialog, QMessageBox
from loguru import logger

import styles
from database import Config

if ty.TYPE_CHECKING:
    from main_window import MainWindow


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

    file_paths = []  # Пути к файлам книг
    roots = []  # Директории с книгами
    for root, _, file_names in os.walk(os.environ["books_folder"]):
        for file_name in file_names:
            file_paths.append(
                os.path.join(root.split(os.environ["books_folder"])[1], file_name)[1:]
            )
        roots.append(root)

    # Копируем книги в новую директорию
    for file_path in file_paths:
        old_file_path = os.path.join(os.environ["books_folder"], file_path)
        new_file_path = pathlib.Path(path, file_path)  # Новый путь к файлу
        logger.opt(colors=True).trace(
            f"Copying <y>{old_file_path}</y> to <y>{new_file_path}</y>"
        )
        if not new_file_path.exists():  # Создаем директорию книги
            new_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old_file_path, new_file_path)  # Копируем
        try:  # Пробуем удалить старый файл
            os.remove(old_file_path)
        except Exception:
            logger.opt(colors=True).exception(
                f"Unable to delete file <y>{old_file_path}</y>."
            )

    for root in roots[::-1]:
        try:  # Пробуем удалить старые директории книг
            os.rmdir(root)
        except Exception:
            logger.opt(colors=True).exception(
                f"Unable to delete directory <y>{root}</y>. "
            )

    old_books_folder = os.environ["books_folder"]
    Config.update(books_folder=path)  # Обновляем настройки в бд и виртуальном окружении
    logger.opt(colors=True).debug(
        "Directory with books changed. "
        f"<y>{old_books_folder}</y> -> <y>{os.environ['books_folder']}</y>"
    )

    main_window.stackedWidget.setCurrentWidget(main_window.settingsPage)
    QMessageBox.information(main_window, "Информация", "Папка успешно изменена")


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

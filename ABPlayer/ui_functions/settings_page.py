"""

Функционал страницы настроек.

"""

from __future__ import annotations

import os
import pathlib
import shutil
import typing as ty

from PyQt5.QtWidgets import QFileDialog, QMessageBox

import styles
from database import Config

if ty.TYPE_CHECKING:
    from main_window import MainWindow


def setDirWithBooks(main_window: MainWindow) -> None:
    """
    Изменяет путь к директории с книгами.
    :param main_window: Экземпляр главного окна.
    """
    # Открываем диалог с пользователем
    path = QFileDialog.getExistingDirectory(main_window, "Выберите папку")
    if path is None or not str(path).strip():
        return

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
        old_file_path = os.path.join(os.environ["books_folder"])
        new_file_path = pathlib.Path(path, file_path)  # Новый путь к файлу
        if not new_file_path.exists():  # Создаем директорию книги
            new_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(old_file_path, new_file_path)  # Копируем
        try:  # Пробуем удалить старый файл
            os.remove(old_file_path)
        except Exception:
            pass

    for root in roots[::-1]:
        try:  # Пробуем удалить старые директории книг
            os.rmdir(root)
        except Exception:
            pass

    Config.update(books_folder=path)  # Обновляем настройки в бд и виртуальном окружении

    main_window.stackedWidget.setCurrentWidget(main_window.settingsPage)
    QMessageBox.information(main_window, "Информация", "Папка успешно изменена")


def changeTheme(main_window: MainWindow) -> None:
    """
    Изменяет тему.
    :param main_window: Экземпляр главного окна.
    """
    main_window.centralwidget.setStyleSheet(
        styles.get_style_sheet(main_window.themeSelecror.currentText())
    )

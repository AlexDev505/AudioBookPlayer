from __future__ import annotations

import os
import typing as ty
from inspect import isclass

# CONFIG SETUP
# Путь к директории приложения
os.environ["APP_DIR"] = os.path.join(os.environ["LOCALAPPDATA"], "AudioBookPlayer")
if not os.path.exists(os.environ["APP_DIR"]):
    os.mkdir(os.environ["APP_DIR"])
# os.environ["APP_DIR"] = "../"
# Путь к базе данных
os.environ["DB_PATH"] = os.path.join(os.environ["APP_DIR"], "database.sqlite")
# Путь к файлу с временными данными
os.environ["TEMP_PATH"] = os.path.join(os.environ["APP_DIR"], "temp.txt")
# Стандартный путь к директории с книгами
os.environ["DEFAULT_BOOKS_FOLDER"] = os.path.join(os.environ["APP_DIR"], "Книги")
if not os.path.exists(os.environ["DEFAULT_BOOKS_FOLDER"]):
    os.mkdir(os.environ["DEFAULT_BOOKS_FOLDER"])
# Версия приложения
os.environ["VERSION"] = "1.0-a"
# Инициализация конфигурации
# (хранил бы в json`е, но нужно несколько таблиц в бд, поэтому вот так вот...)
from database import Config  # noqa

Config.init()

from PyQt5.QtWidgets import QApplication  # noqa

from drivers.exceptions import DriverError  # noqa
from main_window import MainWindow  # noqa
from start_app import StartAppWindow  # noqa


def startApp() -> StartAppWindow:
    """
    Инициализирует окно загрузки.
    """
    window = StartAppWindow()
    window.finished.connect(lambda err: finishLoading(window, err))
    return window


def finishLoading(
    window: StartAppWindow, err: ty.Union[ty.Any, ty.Type[DriverError]]
) -> None:
    """
    Обрабатывает завершение загрузки.
    Открывает главное окно.
    :param window: Окно загрузки.
    :param err: Ошибка.
    """
    window.close()  # Закрываем окно загрузки
    main_window = startMainWindow()
    main_window.show()

    # Если при загрузке возникли ошибки
    if isclass(err) and issubclass(err, DriverError):
        err = err(main_window)
        main_window.openInfoPage(**err.to_dict())
        # Выключаем функционал окна
        main_window.menuBtn.click()
        main_window.menuFrame.setDisabled(True)
        main_window.controlPanel.hide()


def startMainWindow() -> MainWindow:
    """
    Инициализирует главное окно.
    """
    window = MainWindow()
    window.installEventFilter(window)
    return window


def main():
    app = QApplication([])
    window = startApp()
    window.show()
    app.exec()

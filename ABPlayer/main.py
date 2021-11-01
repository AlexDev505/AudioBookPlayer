from __future__ import annotations

import os
import sys
import typing as ty
from inspect import isclass

# CONFIG SETUP
# Путь к директории приложения
# os.environ['APP_DIR'] = os.path.join(os.environ["LOCALAPPDATA"], 'AudioBookPlayer')
os.environ["APP_DIR"] = "../"
# Путь к базе данных
os.environ["DB_PATH"] = os.path.join(os.environ["APP_DIR"], "database.sqlite")
# Путь к файлу с временными данными
os.environ["TEMP_PATH"] = os.path.join(os.environ["APP_DIR"], "temp.txt")
# Версия приложения
os.environ["VERSION"] = "dev1.0.0.0000"
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


if __name__ == "__main__":
    # Временный код
    sys._excepthook = sys.excepthook

    def exception_hook(exctype, value, traceback):
        print(exctype, value, traceback)
        sys._excepthook(exctype, value, traceback)
        # sys.exit(1)

    sys.excepthook = exception_hook
    main()

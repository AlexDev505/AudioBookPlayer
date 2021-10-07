from __future__ import annotations

import typing as ty
from inspect import isclass

from PyQt5.QtWidgets import QApplication

import config  # Noqa
from drivers.exceptions import DriverError
from main_window import MainWindow
from start_app import StartAppWindow


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
    main()

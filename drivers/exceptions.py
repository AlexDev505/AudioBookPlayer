"""

Исключения, возникающие при загрузке приложения.

"""

from __future__ import annotations

import typing as ty
import webbrowser
from inspect import isfunction

from PyQt5.QtWidgets import QMessageBox

if ty.TYPE_CHECKING:
    from main_window import MainWindow


class DriverError(Exception):
    """
    Базовый класс исключения.
    """

    def __init__(self, main_window: MainWindow):
        self._main_window = main_window

    def to_dict(self) -> ty.Dict[str, ty.Any]:
        """
        Конвертирует исключение в словарь
        для дальнейшего отображения ошибки в приложении.
        """
        return {
            k: (self.__getattribute__(k) if isfunction(v) else v)
            for k, v in vars(self.__class__).items()
            if not k.startswith("_")
        }


class ChromeNotFound(DriverError):
    text = "Не установлен браузер Chrome"
    btn_text = "Скачать Chrome"

    def btn_function(self):
        try:
            webbrowser.open_new_tab("https://www.google.com/chrome/")
        except Exception:
            QMessageBox.critical(
                self._main_window,
                "Ошибка",
                "Не удаётся открыть ссылку\nhttps://www.google.com/chrome/",
                buttons=QMessageBox.Close,
                defaultButton=QMessageBox.Close,
            )


class NotAvailableVersion(DriverError):
    text = "Нет драйвера, подходящего для вашей версии Chrome"
    btn_text = "Обновить Chrome"

    def btn_function(self):
        try:
            webbrowser.open_new_tab("https://www.google.com/chrome/")
        except Exception:
            QMessageBox.critical(
                self._main_window,
                "Ошибка",
                "Не удаётся открыть ссылку\nhttps://www.google.com/chrome/",
                buttons=QMessageBox.Close,
                defaultButton=QMessageBox.Close,
            )


class DownloadingFail(DriverError):
    text = "Ошибка при загрузке драйвера.\nПовторите позже."


class ConnectionFail(DriverError):
    text = "Не удалось подключиться к сети.\nПроверьте интернет соединение."

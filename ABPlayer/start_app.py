"""

Окно запуска приложения.
Проверяет подключение к сети, обновляет драйвер браузера,
проверяет целостность системных файлов и файлов книг.

"""

from __future__ import annotations

import typing as ty
from inspect import isclass

import requests
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QMovie
from PyQt5.QtWidgets import QMainWindow

from drivers import chromedriver
from drivers.exceptions import *
from tools import BaseWorker
from ui.start_app import UiStartApp
from ui_functions import window_geometry

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore


class StartAppWindow(QMainWindow, UiStartApp):
    finished: QtCore.pyqtBoundSignal = pyqtSignal(object)
    # Уведомляет о завершении загрузки.
    # :param: ty.Union[ty.Type[DriverError], None]

    def __init__(self):
        super(StartAppWindow, self).__init__()
        self.setupUi(self)

        # Окно без рамки
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Анимация загрузки
        self.loading_movie = QMovie(":/other/loading_app.gif")
        self.loading.setMovie(self.loading_movie)
        self.loading_movie.start()

        self.setupSignals()

        # Создаём новый поток для обновления
        self.worker = Worker(self)
        self.worker.start()

    def setupSignals(self):
        # Подготавливаем область, отвечающую за перемещение окна
        window_geometry.prepareDragZone(self, self.centralwidget)

    def workerChangeStatusHandler(
        self, text: str, err: ty.Union[ty.Type[DriverError], None]
    ) -> None:
        """
        Обрабатывает изменения статуса загрузки.
        :param text: Сообщение.
        :param err: Ошибка.
        """
        self.setStatus(text)

        if isclass(err) and issubclass(err, DriverError):
            self.finished.emit(err)  # Оповещаем о конце загрузки

    def setStatus(self, text: str) -> None:
        """
        Изменяет текст статуса.
        """
        self.status.setText(text)
        self.status.setAlignment(Qt.AlignCenter)


class Worker(BaseWorker):
    status: QtCore.pyqtBoundSignal = pyqtSignal(str, object)
    finished: QtCore.pyqtBoundSignal = pyqtSignal(bool)

    def __init__(self, start_app_window: StartAppWindow):
        super(Worker, self).__init__()
        self.start_app_window = start_app_window

    def connectSignals(self) -> None:
        self.status.connect(
            lambda text, err: self.start_app_window.workerChangeStatusHandler(text, err)
        )
        self.finished.connect(lambda: self.start_app_window.finished.emit(None))

    def worker(self) -> None:
        """
        Процесс, обновления драйвера.
        Выполняется в отдельном потоке.
        """
        self.status.emit("Проверка наличия соединения", None)
        try:
            requests.get("https://www.google.com/", timeout=5)
        except Exception:  # Нет интернет соединения
            self.status.emit("ConnectionError", ConnectionFail)
            return

        try:
            self.status.emit("Проверка наличия браузера", None)
            chromedriver.get_chrome_version()
            self.status.emit("Проверка обновлений драйвера", None)
            chromedriver.install(signal=self.status)
            self.finished.emit(True)  # Оповещаем о конце загрузки
        except IndexError:
            self.status.emit("Chrome Not found", ChromeNotFound)
        except Exception as err:
            if str(err) == "Not available version":
                self.status.emit(str(err), NotAvailableVersion)
            elif str(err) == "Downloading fail":
                self.status.emit(str(err), DownloadingFail)

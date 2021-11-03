"""

Окно запуска приложения.
Проверяет подключение к сети, обновляет драйвер браузера,
проверяет целостность системных файлов и файлов книг.

"""

from __future__ import annotations

import os
import typing as ty
from inspect import isclass
import warnings

import requests
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QMovie
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QMainWindow

from database import Books, Config
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

        # Тень вокруг окна
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Оставляем область вокруг окна, в котором будет отображена тень
        self.centralwidget.layout().setContentsMargins(15, 15, 15, 15)
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)  # Размытие
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(0)  # Смещение
        self.centralwidget.setGraphicsEffect(self.shadow)

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

        self.check_database_integrity()

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

    def check_database_integrity(self):
        self.status.emit("Проверка целостности базы данных", None)

        for table in (Books, Config):
            db = table(os.environ["DB_PATH"])
            fields = db.api.fetchall(f"PRAGMA table_info('{db.table_name}')")
            necessary_fields = db.get_fields()

            if fields[0] != (0, "id", "INTEGER", 1, None, 1) or len(fields[1:]) != len(
                necessary_fields.keys()
            ):
                warnings.warn(
                    f"The number of fields in table `{db.table_name}` does not match"
                )
                return self._restore_database()

            for field, n_field in zip(fields[1:], necessary_fields):
                if field[1] != n_field or field[2] != necessary_fields[n_field]:
                    warnings.warn(
                        f"The field {field[1]}({field[2]}) was encountered, "
                        f"but it should be {n_field}({necessary_fields[n_field]})"
                    )
                    return self._restore_database()

    def _restore_database(self):
        self.status.emit("Восстановление базы данных", None)
        db = Config(os.environ["DB_PATH"])
        db.api.execute("DROP TABLE config")
        db.api.execute("DROP TABLE books")
        db.api.commit()
        db.create_table()
        db.init()
        Books(os.environ["DB_PATH"]).create_table()

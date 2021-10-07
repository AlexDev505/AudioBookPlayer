from __future__ import annotations

from inspect import isclass

from PyQt5 import QtWidgets, QtGui, QtCore

from drivers import chromedriver
from drivers.exceptions import *
from ui.start_app import UiStartApp
from ui_functions import window_geometry
import requests


class StartAppWindow(QtWidgets.QMainWindow, UiStartApp):
    """
    Окно загрузки.
    Обновляет драйвер.
    """

    finished = QtCore.pyqtSignal(object)
    # Уведомляет о завершении загрузки.
    # :param: ty.Union[ty.Type[DriverError], None]

    def __init__(self):
        super(StartAppWindow, self).__init__()
        self.setupUi(self)

        self.setWindowFlags(
            QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)

        self.loading_movie = QtGui.QMovie(":/other/loading_app.gif")
        self.loading.setMovie(self.loading_movie)
        self.loading_movie.start()

        self.setupSignals()

        # Создаём новый поток для обновления
        self.thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.workerChangeStatusHandler)
        self.worker.finished.connect(lambda: self.finished.emit(None))
        self.thread.start()

    def setupSignals(self):
        self.centralwidget.mousePressEvent = (
            lambda e: window_geometry.dragZonePressEvent(self, e)
        )
        self.centralwidget.mouseMoveEvent = lambda e: window_geometry.dragZoneMoveEvent(
            self, e
        )
        self.centralwidget.mouseReleaseEvent = (
            lambda e: window_geometry.dragZoneReleaseEvent(self, e)
        )

    @QtCore.pyqtSlot(str, object)
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
            self.thread.quit()

    def setStatus(self, text: str) -> None:
        """
        Изменяет текст статуса.
        """
        self.status.setText(text)
        self.status.setAlignment(QtCore.Qt.AlignCenter)


class Worker(QtCore.QObject):
    status = QtCore.pyqtSignal(str, object)
    finished = QtCore.pyqtSignal(bool)

    def run(self) -> None:
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

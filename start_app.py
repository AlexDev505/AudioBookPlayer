from __future__ import annotations

from PyQt5 import QtWidgets, QtGui, QtCore

from ui.start_app import UiStartApp
from ui_functions import window_geometry
from drivers import chromedriver


class StartAppWindow(QtWidgets.QMainWindow, UiStartApp):
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

        self.thread = QtCore.QThread()
        self.worker = Worker()
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.status.connect(self.workerChangeStatusHandler)
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

    @QtCore.pyqtSlot(bool, str)
    def workerChangeStatusHandler(self, ok: bool, text: str):
        self.setStatus(text)

    def setStatus(self, text: str):
        self.status.setText(text)
        self.status.setAlignment(QtCore.Qt.AlignCenter)


class Worker(QtCore.QObject):
    status = QtCore.pyqtSignal(bool, str)

    def run(self):
        self.status.emit(True, "Проверка наличия браузера")

        try:
            chromedriver.get_chrome_version()
        except IndexError:
            self.status.emit(False, "")

        try:
            chromedriver.install(signal=self.status)
        except Exception as e:
            self.status.emit(False, str(e))

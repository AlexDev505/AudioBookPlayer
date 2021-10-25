from __future__ import annotations

import os
import ssl
import typing as ty
import urllib.request
import re
from abc import abstractmethod

from PyQt5.QtCore import (
    Qt,
    QUrl,
    QSize,
    QTimer,
    QEvent,
    QThread,
    QObject,
    pyqtSignal,
    pyqtSlot,
    QBasicTimer,
    QEasingCurve,
    QPropertyAnimation,
)
from PyQt5.QtMultimedia import (
    QMediaPlayer,
    QMediaPlaylist,
    QMediaContent,
    QAudioDeviceInfo,
    QAudio,
)
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtWidgets import (
    QLabel,
    QDialog,
    QSlider,
    QToolTip,
    QLineEdit,
    QVBoxLayout,
    QMessageBox,
    QProgressBar,
    QDialogButtonBox,
)

from database import Books
from database.tables.books import Status
from drivers import drivers, BaseDownloadProcessHandler
from tools import convert_into_seconds
from .add_book_page import SearchWorker
from . import sliders

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow
    from database import Book, BookItem
    from ui.item import Item

# Без этого ничего не работает (I ❤ PyQt5 (no.)).
os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"


class PlayerInterface(QObject):
    def __init__(self):
        super(PlayerInterface, self).__init__()

        self.player = Player()
        self.connectSignals()

    def connectSignals(self):
        self.player.player.positionChanged.connect(self._positionChanged)
        self.player.player.stateChanged.connect(self.stateChanged)
        self.player.reloadPlayerInterface.connect(self.reloadPlayerInterface)

    def _positionChanged(self, value: int):
        item = self.player.book.items[self.player.book.stop_flag.item]
        value = value // 1000 - item.start_time

        if value >= item.duration:
            if self.player.book.items.index(item) == len(self.player.book.items) - 1:
                self.player.finish_book()
            else:
                self.player.setPosition(0, self.player.book.stop_flag.item + 1)
        else:
            self.player.book.stop_flag.time = value
            self.positionChanged(value)

    @abstractmethod
    def positionChanged(self, value: int) -> None:
        """
        :param value:
        :return:
        """

    @abstractmethod
    def stateChanged(self, state: QMediaPlayer.State) -> None:
        """
        :param state:
        :return:
        """

    @abstractmethod
    def reloadPlayerInterface(self) -> None:
        """
        :return:
        """


class MainWindowPlayer(PlayerInterface):
    def positionChanged(self, value: int) -> None:
        if self.player.book.url == self.book.url:
            self.current_item_widget.slider.setValue(value)

    def stateChanged(self, state: QMediaPlayer.State) -> None:
        icon = QIcon(
            ":/other/pause.svg"
            if state == QMediaPlayer.PlayingState
            else ":/other/play.svg"
        )
        if self.player.book.url == self.book.url:
            self.playPauseBtnLg.setIcon(icon)
        self.playPauseBtn.setIcon(icon)

    def reloadPlayerInterface(self) -> None:
        if self.player.book.url == self.book.url:
            self.loadPlayer()


class Player(QObject):
    reloadPlayerInterface: QtCore.pyqtSignal = pyqtSignal()

    def __init__(self):
        super(Player, self).__init__()
        self.book: Books = ...

        self.player = QMediaPlayer()
        self.playlist = QMediaPlaylist()
        self.player.setPlaylist(self.playlist)

    def init_book(self, main_window: MainWindow):
        self.book = main_window.book
        self.playlist.clear()

        files: ty.List[str] = []
        for _, _, files in os.walk(self.book.dir_path):
            pass

        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(self.book.dir_path, file)
                url = QUrl.fromLocalFile(file_path)
                self.playlist.addMedia(QMediaContent(url))

        self.playlist.setCurrentIndex(
            self.book.items[self.book.stop_flag.item].file_index - 1
        )
        if self.book.stop_flag.time != 0:
            self.setPosition(self.book.stop_flag.time)

        if main_window.miniPlayerFrame.maximumWidth() == 0:
            main_window.player_animation = QPropertyAnimation(
                main_window.miniPlayerFrame, b"maximumWidth"
            )
            main_window.player_animation.setStartValue(0)
            main_window.player_animation.setEndValue(300)
            main_window.player_animation.setEasingCurve(QEasingCurve.InOutQuart)
            main_window.player_animation.finished.connect(
                lambda: main_window.__dict__.__delitem__("player_animation")
            )  # Удаляем анимацию
            main_window.player_animation.start()

        # TODO: Изменение устройства вывода
        scv = self.player.service()
        out = scv.requestControl("org.qt-project.qt.audiooutputselectorcontrol/5.0")
        allAvailableOutputs = out.availableOutputs()
        availableOutputs = {}
        for output in allAvailableOutputs:
            key = re.search(r"\\.+{(?P<key>.+)}", output)
            if key:
                key = key.group("key")
                if key not in availableOutputs:
                    availableOutputs[key] = output
        availableOutputs = {
            re.sub(r"^.+?: ", "", out.outputDescription(output)): output
            for output in availableOutputs.values()
        }  # {<device name>: <id>}

        out.setActiveOutput(
            "@device:cm:{E0F158E1-CB04-11D0-BD4E-00A0C911CE86}\\DirectSound:{A009F969-4D9B-4753-A01A-999E649A5812}"
        )  # put device id
        scv.releaseControl(out)

    def finish_book(self):
        self.book.status = Status.finished
        self.book.stop_flag.item = 0
        self.book.stop_flag.time = 0
        self.book.save()
        self.setPosition(0, 0)
        self.player.pause()

    def setPosition(self, position: int, item: int = None) -> None:
        self.book.stop_flag.time = position
        item = item if item is not None else self.book.stop_flag.item
        if item != self.book.stop_flag.item:
            if (
                self.book.items[item].file_index
                != self.book.items[self.book.stop_flag.item].file_index
            ):
                self.playlist.setCurrentIndex(self.book.items[item].file_index - 1)
            self.book.stop_flag.item = item
            self.reloadPlayerInterface.emit()
        self.player.setPosition((self.book.items[item].start_time + position) * 1000)

    def rewindToPast(self, step: int = 15) -> None:
        time, item = self.book.stop_flag.time, self.book.stop_flag.item
        time -= step
        if time < 0:
            if item == 0:
                time = 0
            else:
                item -= 1
                time = self.book.items[item].duration + time
        self.setPosition(time, item)

    def rewindToFuture(self, step: int = 15) -> None:
        time, item = self.book.stop_flag.time, self.book.stop_flag.item
        time += step
        if time >= self.book.items[item].duration:
            if item == len(self.book.items) - 1:
                time = self.book.items[-1].end_time
            else:
                time = time - self.book.items[item].duration
                item += 1
        self.setPosition(time, item)

    def setVolume(self, value: int):
        self.player.setVolume(value)

    def setSpeed(self, value: int):
        pass

    def playPause(self, main_window: MainWindow) -> None:
        if self.book != main_window.book:
            self.player.stop()
        self.setState(main_window)

    def setState(self, main_window: MainWindow):
        if self.player.state() == QMediaPlayer.StoppedState:
            self.init_book(main_window)

        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()


def selectItem(main_window: MainWindow, event: QEvent, item_widget: Item) -> None:
    if event.pos() not in item_widget.rect() or event.button() != Qt.LeftButton:
        return

    book: Books = main_window.player.book
    if book is ... or book.url != main_window.book.url:
        main_window.player.setState(main_window)
        book: Books = main_window.player.book

    main_window.player.setPosition(0, book.items.index(item_widget.item))


def showProgress(main_window: MainWindow, value: int, item_widget: Item) -> None:
    book: Books = main_window.player.book
    if book is ...:
        main_window.player.setState(main_window)
        book: Books = main_window.player.book

    # Отображаем прогресс прослушивания
    main_window.progressLabel.setText(f"{book.listening_progress} прослушано")
    item_widget.doneTime.setText(convert_into_seconds(value))


def moveProgress(main_window: MainWindow, book: Books) -> None:
    main_window.current_item_widget.slider.valueChanged.disconnect()
    main_window.current_item_widget.slider.setValue(book.stop_flag.time)
    main_window.current_item_widget.slider.valueChanged.connect(
        lambda value: showProgress(main_window, value, main_window.current_item_widget)
    )


def sliderMouseReleaseEvent(
    main_window: MainWindow, event: QEvent, slider: QSlider
) -> None:
    sliders.mouseReleaseEvent(event, slider)
    main_window.player.setPosition(slider.value())

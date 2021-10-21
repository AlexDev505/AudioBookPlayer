from __future__ import annotations

import os
import ssl
import typing as ty
import urllib.request

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
from PyQt5.QtMultimedia import QMediaPlayer, QMediaPlaylist, QMediaContent
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtWidgets import (
    QLabel,
    QDialog,
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

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow
    from database import Book, BookItem
    from ui.item import Item


class Player(QObject):
    playSignal: QtCore.pyqtSignal = pyqtSignal()
    pauseSignal: QtCore.pyqtSignal = pyqtSignal()
    nextSignal: QtCore.pyqtSignal = pyqtSignal()
    previousSignal: QtCore.pyqtSignal = pyqtSignal()
    setVolumeSignal: QtCore.pyqtSignal = pyqtSignal(int)
    setSpeedSignal: QtCore.pyqtSignal = pyqtSignal(int)

    def __init__(self, main_window: MainWindow):
        super(Player, self).__init__()
        self.main_window = main_window
        self.book: Books = ...

        self.player = QMediaPlayer()
        self.playlist = QMediaPlaylist()
        self.player.setPlaylist(self.playlist)

        self.player.positionChanged.connect(self.positionChanged)
        self.playSignal.connect(self.player.play)
        self.pauseSignal.connect(self.player.pause)
        self.nextSignal.connect(self.next)
        self.previousSignal.connect(self.previous)
        self.setVolumeSignal.connect(self.setVolumeSignal)

    def init_book(self, book: Books):
        item: BookItem
        self.book = book
        self.playlist.clear()

        files: ty.List[str] = []
        for _, _, files in os.walk(book.dir_path):
            pass

        for file in files:
            if file.endswith(".mp3"):
                file_path = os.path.join(book.dir_path, file)
                url = QUrl.fromLocalFile(file_path)
                self.playlist.addMedia(QMediaContent(url))

        if self.main_window.miniPlayerFrame.maximumWidth() == 0:
            self.main_window.player_animation = QPropertyAnimation(
                self.main_window.miniPlayerFrame, b"maximumWidth"
            )
            self.main_window.player_animation.setStartValue(0)
            self.main_window.player_animation.setEndValue(300)
            self.main_window.player_animation.setEasingCurve(QEasingCurve.InOutQuart)
            self.main_window.player_animation.finished.connect(
                lambda: self.main_window.__dict__.__delitem__("player_animation")
            )  # Удаляем анимацию
            self.main_window.player_animation.start()

    def next(self):
        self.playlist.next()

    def previous(self):
        self.playlist.previous()

    def setVolume(self, value: int):
        self.player.setVolume(value)

    def setSpeed(self, value: int):
        pass

    def positionChanged(self, value: int):
        value //= 1000
        self.book.stop_flag.time = value
        self.main_window.current_item_widget.doneTime.setText(
            convert_into_seconds(value)
        )
        moveProgress(self.main_window, self.book)


def selectItem(main_window: MainWindow, event: QEvent, item_widget: Item) -> None:
    if event.pos() not in item_widget.rect() or event.button() != Qt.LeftButton:
        return

    book: Books = main_window.book
    book.stop_flag.item = book.items.index(item_widget.item)
    book.stop_flag.time = 0

    main_window.loadPlayer()


def rewindTo(main_window: MainWindow, direction: ty.Literal["past", "future"]) -> None:
    book: Books = main_window.book
    _index = book.stop_flag.item
    if direction == "past":
        book.stop_flag.time -= 15
        if book.stop_flag.time < 0:
            if book.stop_flag.item == 0:
                book.stop_flag.time = 0
            else:
                book.stop_flag.item -= 1
                book.stop_flag.time = (
                    book.items[book.stop_flag.item].duration + book.stop_flag.time
                )
    else:
        book.stop_flag.time += 15
        if book.stop_flag.time >= book.items[book.stop_flag.item].duration:
            if book.stop_flag.item == len(book.items) - 1:
                book.stop_flag.time = book.items[-1].end_time
            else:
                book.stop_flag.time = (
                    book.stop_flag.time - book.items[book.stop_flag.item].duration
                )
                book.stop_flag.item += 1

    if _index != book.stop_flag.item:
        main_window.loadPlayer()
    else:
        # Отображаем прогресс прослушивания
        main_window.progressLabel.setText(f"{book.listening_progress} прослушано")
        main_window.current_item_widget.slider.setValue(
            int(book.stop_flag.time / (book.items[book.stop_flag.item].duration / 100))
        )
        main_window.current_item_widget.doneTime.setText(
            convert_into_seconds(book.stop_flag.time)
        )


def setTime(main_window: MainWindow, value: int, item_widget: Item) -> None:
    book: Books = main_window.book
    book.stop_flag.time = int(item_widget.item.duration / 100 * value)

    # Отображаем прогресс прослушивания
    main_window.progressLabel.setText(f"{book.listening_progress} прослушано")
    item_widget.doneTime.setText(convert_into_seconds(book.stop_flag.time))


def moveProgress(main_window: MainWindow, book: Books) -> None:
    main_window.current_item_widget.slider.valueChanged.disconnect()
    main_window.current_item_widget.slider.setValue(
        int(book.stop_flag.time / (book.items[book.stop_flag.item].duration / 100))
    )
    main_window.current_item_widget.slider.valueChanged.connect(
        lambda value: setTime(main_window, value, main_window.current_item_widget)
    )


def playPause(main_window: MainWindow) -> None:
    main_window.player.init_book(main_window.book)
    main_window.player.playSignal.emit()

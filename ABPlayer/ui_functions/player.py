from __future__ import annotations

import os
import typing as ty
from abc import abstractmethod

from PyQt5.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QTimer,
    QUrl,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QIcon
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QMediaPlaylist

from database import Books
from database.tables.books import Status
from tools import convert_into_seconds
from . import sliders
from .book_page import loadPreview

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from PyQt5.QtCore import QEvent
    from PyQt5.QtWidgets import QSlider
    from main_window import MainWindow
    from ui.item import Item

# Это исправляет проблему с загрузкой некоторых аудиофайлов,
# но в то же время отнимает возможность изменять устройство вывода (I ❤ PyQt5 (no.)).
os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"


class BasePlayerInterface(QObject):
    """
    Базовый класс интерфейса плеера.
    Реализует отображение данных плеера в интерфейсе.
    """

    def __init__(self):
        super(BasePlayerInterface, self).__init__()

        self.player = Player()
        self.connectSignals()

        self._last_saved_item = 0
        self._last_saved_time = 0

    def connectSignals(self) -> None:
        self.player.player.positionChanged.connect(self._positionChanged)
        self.player.player.stateChanged.connect(self._stateChanged)
        self.player.reloadPlayerInterface.connect(self.reloadPlayerInterface)

    def reset_last_save(self) -> None:
        self._last_saved_time = self._last_saved_item = 0

    def _positionChanged(self, value: int) -> None:
        # Я не знаю почему и где, но он может вызваться, когда книга не инициализирована
        if self.player.book is ...:
            return

        item = self.player.book.items[self.player.book.stop_flag.item]
        value = value // 1000 - item.start_time

        if value >= item.duration:  # Глава закончилась
            if self.player.book.items.index(item) != len(self.player.book.items) - 1:
                # Переходим к следующей главе
                self.player.setPosition(0, self.player.book.stop_flag.item + 1)
            else:  # Книга закончилась
                self.player.player.stop()
            return
        else:
            self.player.book.stop_flag.time = value
            self.positionChanged(value)

        # Сохраняем позицию прослушивания каждые 10 секунд
        if (
            abs(self.player.book.stop_flag.time - self._last_saved_time) >= 10
            or self._last_saved_item != self.player.book.stop_flag.item
        ):
            self.player.book.save()
            self._last_saved_time = self.player.book.stop_flag.time
            self._last_saved_item = self.player.book.stop_flag.item

    @abstractmethod
    def positionChanged(self, value: int) -> None:
        """
        Необходимо реализовать в наследуемом классе.
        Вызывается при изменении позиции плеера.
        :param value: Позиция прослушивания в секундах.
        """

    def _stateChanged(self, state: QMediaPlayer.State) -> None:
        if state == QMediaPlayer.StoppedState:
            if (
                abs(
                    self.player.book.items[self.player.book.stop_flag.item].duration
                    - self.player.book.stop_flag.time
                )
                <= 10
            ):
                self.player.finish_book()
        self.stateChanged(state)

    @abstractmethod
    def stateChanged(self, state: QMediaPlayer.State) -> None:
        """
        Необходимо реализовать в наследуемом классе.
        Вызывается при изменении состояния плеера.
        :param state: Новое состояние (Остановлен, На паузе, Играет).
        """

    @abstractmethod
    def reloadPlayerInterface(self) -> None:
        """
        Необходимо реализовать в наследуемом классе.
        Вызывается, когда необходимо обновить интерфейс плеера.
        """


class MainWindowPlayer(BasePlayerInterface):
    """
    Взаимодействие плеера с главным окном.
    """

    def positionChanged(self, value: int) -> None:
        # Если открыта страница прослушиваемой книги
        if self.player.book.url == self.book.url:
            if not self.current_item_widget.slider.__dict__.get("pressed"):
                self.current_item_widget.slider.setValue(value)

    def stateChanged(self, state: QMediaPlayer.State) -> None:
        icon = QIcon(
            ":/other/pause.svg"
            if state == QMediaPlayer.PlayingState
            else ":/other/play.svg"
        )
        # Если открыта страница прослушиваемой книги
        if self.player.book.url == self.book.url:
            self.playPauseBtnLg.setIcon(icon)
        self.playPauseBtn.setIcon(icon)

    def reloadPlayerInterface(self) -> None:
        # Если открыта страница прослушиваемой книги
        if self.player.book.url == self.book.url:
            self.loadPlayer()


class Player(QObject):
    """
    Аудио плеер.
    """

    reloadPlayerInterface: QtCore.pyqtSignal = pyqtSignal()

    def __init__(self):
        super(Player, self).__init__()
        self.book: Books = ...  # Прослушиваемая книга

        self.player = QMediaPlayer()
        # TODO: Загружать громкость из файла с временными данными
        self.player.setVolume(50)  # Громкость по умолчанию
        self.playlist = QMediaPlaylist()
        self.player.setPlaylist(self.playlist)

    def init_book(self, main_window: MainWindow) -> None:
        """
        Загружает книгу в плейлист.
        :param main_window: Экземпляр главного окна.
        """
        self.book = main_window.book
        stop_flag_time = self.book.stop_flag.time
        main_window.reset_last_save()

        # Изменяем статс книги
        self.book.status = Status.started
        self.book.save()

        self.playlist.clear()  # Очищаем плейлист

        # Загружаем аудио файлы в плейлист
        for _, _, files in os.walk(self.book.dir_path):
            for file in files:
                if file.endswith(".mp3"):
                    file_path = os.path.join(self.book.dir_path, file)
                    url = QUrl.fromLocalFile(file_path)
                    self.playlist.addMedia(QMediaContent(url))
            break

        self.playlist.setCurrentIndex(
            self.book.items[self.book.stop_flag.item].file_index - 1
        )  # Выбираем файл, на котором остановились
        if stop_flag_time != 0:
            # Перемещаемся в точку остановки
            self.setPosition(stop_flag_time, delay=250)

        # TODO: Инициализировать книгу из файла с временными данными
        # Открываем мини плеер
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

        main_window.bookNameLabel.setText(self.book.name)
        main_window.bookAuthorLabel.setText(self.book.author)
        loadPreview(main_window, main_window.bookCover, (60, 60), self.book)

    def finish_book(self) -> None:
        """
        Помечает книгу как прочитанную.
        """
        self.setPosition(0, 0, 0)
        self.player.pause()
        self.book.status = Status.finished
        self.book.stop_flag.item = 0
        self.book.stop_flag.time = 0
        self.book.save()

    def setPosition(self, position: int, item: int = None, delay=100) -> None:
        """
        Изменяет позицию прослушивания.
        :param position: Новая позиция(в секундах).
        :param item: Индекс главы.
        :param delay: Задержка перед изменением позиции.
        """
        # TODO: работает коряво. Плеер успевает изменить позицию,
        #  из-за чего слайдер дергается перед окончательной сменой позиции.
        self.book.stop_flag.time = position
        item = item if item is not None else self.book.stop_flag.item
        if item != self.book.stop_flag.item:  # Переместились на новую главу.
            self.book.stop_flag.item = item
            self.reloadPlayerInterface.emit()  # Обновляем интерфейс плеера
            # переход к новому файлу
            if self.book.items[item].file_index != self.book.items[item - 1].file_index:
                self.player.pause()
                self.playlist.setCurrentIndex(self.book.items[item].file_index - 1)
                # Если после `self.playlist.setCurrentIndex`
                # сразу вызвать `self.player.setPosition`,
                # то аудио файл начнет проигрываться сначала
                self._setPosition(
                    (self.book.items[item].start_time + position),
                    250 if delay == 100 else delay,
                )
                return
        self._setPosition((self.book.items[item].start_time + position), delay)

    def _setPosition(self, position: int, delay: int) -> None:
        if delay == 0:
            self.player.setPosition(position * 1000)
            self.player.play()
        else:
            QTimer.singleShot(
                delay,
                lambda: (
                    self.player.setPosition(position * 1000),
                    self.player.play(),
                ),
            )

    def rewindToPast(self, step: int = 15) -> None:
        """
        Перемещает позицию назад.
        :param step: Шаг, на который нужно переместиться (в секундах).
        """
        time, item = self.book.stop_flag.time, self.book.stop_flag.item
        time -= step
        if time < 0:
            if item == 0:
                time = 0
            else:
                item -= 1
                time += self.book.items[item].duration
        self.setPosition(time, item)

    def rewindToFuture(self, step: int = 15) -> None:
        """
        Перемещает позицию вперед.
        :param step: Шаг, на который нужно переместиться (в секундах).
        """
        time, item = self.book.stop_flag.time, self.book.stop_flag.item
        time += step
        if time >= self.book.items[item].duration:
            if item == len(self.book.items) - 1:
                time = self.book.items[-1].end_time
            else:
                time -= self.book.items[item].duration
                item += 1
        self.setPosition(time, item)

    def playPause(self, main_window: MainWindow) -> None:
        """
        Обрабатывает нажатие на кнопку play/pause на странице книги.
        :param main_window: Экземпляр главного окна.
        """
        # Если мы включаем другую книгу
        if self.book is ... or self.book.url != main_window.book.url:
            self.player.stop()  # Останавливаем прослушивание
        self.setState(main_window)

    def setState(self, main_window: MainWindow) -> None:
        """
        Обрабатывает нажатие на кнопку play/pause на панели управления.
        :param main_window: Экземпляр главного окна.
        """
        if self.player.state() == QMediaPlayer.StoppedState:
            self.init_book(main_window)  # Инициализируем книгу

        # Изменяем состояние
        if self.player.state() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()


def selectItem(main_window: MainWindow, event: QEvent, item_widget: Item) -> None:
    """
    Обрабатывает отпускание кнопки мыши с неактивного элемента в списке глав.
    :param main_window: Экземпляр главного окна.
    :param event:
    :param item_widget: Экземпляр виджета главы.
    """
    # Если пользователь отпустил кнопку мыши, когда курсор находился на виджете
    if event.pos() not in item_widget.rect() or event.button() != Qt.LeftButton:
        return

    book: Books = main_window.player.book
    # Если пользователь включает другую книгу
    if book is ... or book.url != main_window.book.url:
        main_window.player.player.stop()
        main_window.player.setState(main_window)
        book: Books = main_window.player.book

    main_window.player.setPosition(0, book.items.index(item_widget.item))


def showProgress(main_window: MainWindow, value: int, item_widget: Item) -> None:
    """
    Вызывается при изменении значения QSlider.
    Отображает прогресс прослушивания главы.
    :param main_window: Экземпляр главного окна.
    :param value: Позиция.
    :param item_widget: Экземпляр виджета главы.
    """
    book: Books = main_window.player.book
    if book is ...:
        main_window.player.setState(main_window)
        book: Books = main_window.player.book

    # Отображаем прогресс прослушивания
    main_window.progressLabel.setText(f"{book.listening_progress} прослушано")
    item_widget.doneTime.setText(convert_into_seconds(value))


def sliderMouseReleaseEvent(
    main_window: MainWindow, event: QEvent, slider: QSlider
) -> None:
    """
    Вызывается при отпускании кнопки мыши с QSlider.
    :param main_window: Экземпляр главного окна.
    :param event:
    :param slider: Отправитель события.
    """
    sliders.mouseReleaseEvent(slider, event)

    if event.button() == Qt.LeftButton:
        book: Books = main_window.player.book
        if book is ... or book.url != main_window.book.url:
            main_window.player.player.stop()
            main_window.player.setState(main_window)

        main_window.player.setPosition(slider.value(), delay=250)

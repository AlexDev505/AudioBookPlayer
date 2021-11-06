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
from PyQt5.QtWidgets import QMessageBox
from loguru import logger

import temp_file
from database import Books, Book
from database.tables.books import Status
from tools import convert_into_seconds, get_file_hash, pretty_view
from . import sliders
from .book_page import DeleteBookWorker

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
        self.player.bookIsDamaged.connect(self.bookIsDamaged)

    def reset_last_save(self) -> None:
        self._last_saved_time = self._last_saved_item = 0

    @logger.catch
    def _positionChanged(self, value: int) -> None:
        # Я не знаю почему и где, но он может вызваться, когда книга не инициализирована
        if self.player.book is ...:
            return

        item = self.player.book.items[self.player.book.stop_flag.item]
        value = value // 1000 - item.start_time
        logger.opt(colors=True).trace(f"Position changed: <y>{value}</y>")

        if value >= item.duration:  # Глава закончилась
            logger.trace("The chapter is over")
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
            logger.trace("Stop flag saved")

    @abstractmethod
    def positionChanged(self, value: int) -> None:
        """
        Необходимо реализовать в наследуемом классе.
        Вызывается при изменении позиции плеера.
        :param value: Позиция прослушивания в секундах.
        """

    @logger.catch
    def _stateChanged(self, state: QMediaPlayer.State) -> None:
        logger.opt(colors=True).trace(f"State changed: <y>{state}</y>")
        if state == QMediaPlayer.StoppedState:
            if (
                self.player.book is not ...
                and self.player.book.stop_flag.item == len(self.player.book.items) - 1
                and abs(
                    self.player.book.items[self.player.book.stop_flag.item].duration
                    - self.player.book.stop_flag.time
                )
                <= 10
            ):
                self.player.finish_book()
                self.player.book = ...
                return
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

    @abstractmethod
    def bookIsDamaged(self) -> None:
        """
        Необходимо реализовать в наследуемом классе.
        Вызывается, когда файлы книги повреждены.
        """


class MainWindowPlayer(BasePlayerInterface):
    """
    Взаимодействие плеера с главным окном.
    """

    def positionChanged(self, value: int) -> None:
        # Если открыта страница прослушиваемой книги
        if self.player.book.url == self.book.url:
            if (
                self.current_item_widget is not ...
                and not self.current_item_widget.slider.__dict__.get("pressed")
            ):
                self.current_item_widget.slider.setValue(value)

    def stateChanged(self, state: QMediaPlayer.State) -> None:
        icon = QIcon(
            ":/other/pause.svg"
            if state == QMediaPlayer.PlayingState
            else ":/other/play.svg"
        )
        # Если открыта страница прослушиваемой книги
        if self.player.book is ... or self.player.book.url == self.book.url:
            self.playPauseBtnLg.setIcon(icon)
        self.playPauseBtn.setIcon(icon)

    def reloadPlayerInterface(self) -> None:
        # Если открыта страница прослушиваемой книги
        if self.player.book.url == self.book.url:
            self.loadPlayer()

    @logger.catch
    def bookIsDamaged(self) -> None:
        self.openLoadingPage()
        QMessageBox.information(
            self, "Внимание", "Файлы повреждены.\nСкачайте книгу заново."  # noqa
        )
        downloaded_book = self.player.book
        book = Book(
            **{
                k: v
                for k, v in downloaded_book.__dict__.items()
                if k in Book.__annotations__
            }  # noqa
        )
        self.player.book = ...

        # Создаем и запускаем новый поток
        self.DeleteBookWorker = DeleteBookWorker(self, downloaded_book)  # noqa
        self.DeleteBookWorker.start()
        self.DeleteBookWorker.finished.disconnect()  # noqa
        self.DeleteBookWorker.finished.connect(lambda: self.openBookPage(book))  # noqa

        last_listened_book_id = temp_file.load().get("last_listened_book_id")
        if last_listened_book_id == downloaded_book.id:
            temp_file.delete_items("last_listened_book_id")
            if self.miniPlayerFrame.maximumWidth() != 0:
                self.miniPlayerFrame.player_animation = QPropertyAnimation(
                    self.miniPlayerFrame, b"maximumWidth"
                )
                self.miniPlayerFrame.player_animation.setStartValue(300)
                self.miniPlayerFrame.player_animation.setEndValue(0)
                self.miniPlayerFrame.player_animation.setEasingCurve(
                    QEasingCurve.InOutQuart
                )
                self.miniPlayerFrame.player_animation.finished.connect(
                    lambda: self.miniPlayerFrame.__dict__.__delitem__(
                        "player_animation"
                    )
                )  # Удаляем анимацию
                self.miniPlayerFrame.player_animation.start()


class Player(QObject):
    """
    Аудио плеер.
    """

    reloadPlayerInterface: QtCore.pyqtSignal = pyqtSignal()
    bookIsDamaged: QtCore.pyqtSignal = pyqtSignal()

    def __init__(self):
        super(Player, self).__init__()
        self.book: Books = ...  # Прослушиваемая книга

        self.player = QMediaPlayer()
        self.player.setVolume(50)  # Громкость по умолчанию
        self.playlist = QMediaPlaylist()
        self.player.setPlaylist(self.playlist)

    @logger.catch
    def init_book(self, main_window: MainWindow, book: Books) -> None:
        """
        Загружает книгу в плейлист.
        :param main_window: Экземпляр главного окна.
        :param book: Экземпляр скачанной книги.
        """
        logger.opt(colors=True).debug(
            "Book initialization. Book:"
            + pretty_view(
                {k: v for k, v in book.__dict__.items() if not k.startswith("_")}
            ),
        )
        self.book = book
        stop_flag_time = self.book.stop_flag.time
        main_window.reset_last_save()

        # Обновляем данные о последней прослушиваемой книги
        temp_file.update(last_listened_book_id=self.book.id)

        # Изменяем статс книги
        self.book.status = Status.started
        self.book.save()

        self.playlist.clear()  # Очищаем плейлист

        # Загружаем аудио файлы в плейлист
        file_paths: ty.List[str] = []
        if not os.path.isdir(self.book.dir_path):  # Директории нет
            logger.opt(colors=True).error(
                f"Directory <y>{self.book.dir_path}<y> does not exist"
            )
            return self.bookIsDamaged.emit()

        for file_name, file_hash in self.book.files.items():
            file_path = os.path.join(self.book.dir_path, file_name)
            if not os.path.isfile(file_path) or get_file_hash(file_path) != file_hash:
                logger.opt(colors=True).error(f"File <y>{file_path}</y> is damaged.")
                return self.bookIsDamaged.emit()
            file_paths.append(file_path)

        for file_path in file_paths:
            url = QUrl.fromLocalFile(file_path)
            self.playlist.addMedia(QMediaContent(url))

        self.playlist.setCurrentIndex(
            self.book.items[self.book.stop_flag.item].file_index - 1
        )  # Выбираем файл, на котором остановились
        if stop_flag_time != 0:
            # Перемещаемся в точку остановки
            self.setPosition(stop_flag_time, delay=250)

        main_window.loadMiniPlayer()

    @logger.catch
    def finish_book(self) -> None:
        """
        Помечает книгу как прочитанную.
        """
        logger.trace("Completion of the book")
        self.setPosition(0, 0, 250)
        self.book.status = Status.finished
        self.book.stop_flag.item = 0
        self.book.stop_flag.time = 0
        self.book.save()
        logger.opt(colors=True).debug(
            f"The book has been listened. book.id=<y>{self.book.id}</y>"
        )
        QTimer.singleShot(300, self.player.stop)
        self.reloadPlayerInterface.emit()

    @logger.catch
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
            logger.opt(colors=True).debug(
                f"Chapter change. <y>{self.book.stop_flag.item}</y> -> <y>{item}</y>"
            )
            self.book.stop_flag.item = item
            self.reloadPlayerInterface.emit()  # Обновляем интерфейс плеера
            # переход к новому файлу
            if self.book.items[item].file_index != self.book.items[item - 1].file_index:
                logger.opt(colors=True).debug(
                    "Audio file change. "
                    f"<y>{self.book.items[item - 1].file_index}</y> "
                    f"-> <y>{self.book.items[item].file_index}</y>"
                )
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
        logger.opt(colors=True).trace(f"Position change to <y>{position}</y>")
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

    @logger.catch
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

    @logger.catch
    def rewindToFuture(self, step: int = 15) -> None:
        """
        Перемещает позицию вперед.
        :param step: Шаг, на который нужно переместиться (в секундах).
        """
        time, item = self.book.stop_flag.time, self.book.stop_flag.item
        time += step
        if time >= self.book.items[item].duration:
            if item == len(self.book.items) - 1:
                self.player.stop()
                return
            else:
                time -= self.book.items[item].duration
                item += 1
        self.setPosition(time, item)

    @logger.catch
    def playPause(self, main_window: MainWindow) -> None:
        """
        Обрабатывает нажатие на кнопку play/pause на странице книги.
        :param main_window: Экземпляр главного окна.
        """
        # Если мы включаем другую книгу
        if self.book is ... or self.book.url != main_window.book.url:
            self.player.stop()  # Останавливаем прослушивание
            self.book = ...
        self.setState(main_window)

    @logger.catch
    def setState(self, main_window: MainWindow) -> None:
        """
        Обрабатывает нажатие на кнопку play/pause на панели управления.
        :param main_window: Экземпляр главного окна.
        """
        if self.player.state() == QMediaPlayer.StoppedState:
            self.init_book(
                main_window,
                book=self.book if self.book is not ... else main_window.book,
            )  # Инициализируем книгу

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

    logger.opt(colors=True).trace(
        "Changed chapter: " + pretty_view(item_widget.item.__dict__),
    )
    main_window.player.playPause(main_window)
    main_window.player.setPosition(
        0, main_window.player.book.items.index(item_widget.item), delay=300
    )


def showProgress(main_window: MainWindow, value: int, item_widget: Item) -> None:
    """
    Вызывается при изменении значения QSlider.
    Отображает прогресс прослушивания главы.
    :param main_window: Экземпляр главного окна.
    :param value: Позиция.
    :param item_widget: Экземпляр виджета главы.
    """
    if main_window.player.book is ...:
        main_window.player.playPause(main_window)

    main_window.progressLabel.setText(
        f"{main_window.player.book.listening_progress} прослушано"
    )
    item_widget.doneTime.setText(convert_into_seconds(value))
    logger.opt(colors=True).trace(
        f"Listening progress is displayed. "
        f"Value=<y>{value}</y> "
        f"Progress=<y>{main_window.progressLabel.text()}</y> "
        f"Time=<y>{item_widget.doneTime.text()}</y>"
    )


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
        position = slider.value()
        logger.opt(colors=True).trace(
            f"Player position changed by slider. Value=<y>{position}</y>"
        )
        main_window.player.playPause(main_window)
        main_window.player.setPosition(position, delay=250)

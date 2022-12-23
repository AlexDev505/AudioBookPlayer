from __future__ import annotations

import hashlib
import os
import pathlib
import ssl
import subprocess
import sys
import time
import typing as ty
import urllib.request
import webbrowser
from contextlib import suppress
from enum import Enum

import msgspec
from PyQt5.QtCore import (
    pyqtSignal,
    QTimer,
)
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMessageBox
from loguru import logger

from database import Books
from database.tables.books import BookFiles, DateTime
from drivers import drivers, BaseDownloadProcessHandler
from tools import (
    BaseWorker,
    convert_into_bytes,
    get_file_hash,
    send_system_notification,
)

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow
    from ui import UiBookSeriesItem
    from drivers.base import Driver
    from database.tables.books import Book


class DownloadingState(Enum):
    waiting = "Ожидание..."
    preparing = "Подготовка..."
    downloading = "Скачивание..."
    done = "Скачивание завершено"
    canceled = "Скачивание прервано"


class GettingBookSeries(BaseWorker):
    """
    Класс реализующий поиск книг из той же серии.
    """

    finished: QtCore.pyqtSignal = pyqtSignal(object)  # Поиск завершен
    failed: QtCore.pyqtSignal = pyqtSignal(str)  # Ошибка при поиске

    def __init__(self, main_window: MainWindow, drv: Driver, url: str):
        super(GettingBookSeries, self).__init__()
        self.main_window, self.drv, self.url = main_window, drv, url

    def connectSignals(self) -> None:
        self.finished.connect(lambda books: self.finish(books))
        self.failed.connect(lambda message: self.fail(message))

    def worker(self) -> None:
        logger.opt(colors=True).debug(
            "Starting the series search process. "
            f'Url=<y>{self.url}</y> Drv=<y>{self.drv.driver_name}</y>"'
        )
        self.main_window.setLock(True)
        try:
            books = self.drv.get_book_series(self.url)
            self.finished.emit(books)
        except Exception as err:
            if "ERR_INTERNET_DISCONNECTED" in str(err):
                self.failed.emit(
                    "Не удалось подключиться к серверу.\n"
                    "Проверьте интернет соединение."
                )
            elif "chromedriver" in str(err):
                self.failed.emit(
                    "Не удалось получить данные об этой книге.\n"
                    "Проверьте интернет соединение и перезапустите приложение."
                )
            else:
                self.failed.emit("Не удалось получить данные об этой книге.\n")
                logger.exception("Series search failed")
        self.main_window.setLock(False)
        del self.drv

    def finish(self, books: list[Book]) -> None:
        self.main_window.openBookSeriesPage(books)

    def fail(self, message: str) -> None:
        self.main_window.openInfoPage(
            text=message,
            btn_text="Открыть книгу в браузере",
            btn_function=lambda: webbrowser.open_new_tab(self.url),
        )


def open_book_series_page(main_window: MainWindow, books=None) -> None:
    if books:
        main_window.openBookSeriesPage(books)
        return
    if (
        main_window.downloadable_book is not ...
        or main_window.downloadable_book_series is not ...
    ):
        if main_window.downloadable_book_series is ... or not any(
            main_window.book.url == book.url
            for book in main_window.downloadable_book_series
        ):
            QMessageBox.information(
                main_window,
                "Предупреждение",
                "Дождитесь окончания скачивания другой книги",
            )
            return
        else:
            main_window.openBookSeriesPage(main_window.downloadable_book_series)
            return

    if not main_window.book.series_name:
        main_window.downloadBookSeriesBtn.hide()
        return

    main_window.openLoadingPage()

    # Драйвер не найден
    driver = main_window.book.driver
    if not any(driver == drv.driver_name for drv in drivers):
        main_window.openInfoPage(
            text="Драйвер для данного сайта не найден",
            btn_text="Вернуться",
            btn_function=lambda: main_window.stackedWidget.setCurrentWidget(
                main_window.addBookPage
            ),
        )
        return

    drv = [drv for drv in drivers if driver == drv.driver_name][0]()

    # Создаём и запускаем новый поток
    main_window.searchWorker = GettingBookSeries(main_window, drv, main_window.book.url)
    main_window.searchWorker.start()


def toggleBookSeriesItem(bookWidget: UiBookSeriesItem) -> None:
    """
    Изменяет иконку кнопки.
    """
    if not bookWidget.checkboxBtn.isChecked():
        bookWidget.checkboxBtn.setIcon(QIcon())
    else:
        bookWidget.checkboxBtn.setIcon(QIcon(":/other/check.svg"))
    logger.opt(colors=True).debug(
        f"Book series item {id(bookWidget)} checkbox state changed: "
        f"<y>{bookWidget.checkboxBtn.isChecked()}</y>"
    )


def toggleAll(main_window: MainWindow) -> None:
    for bookWidget in main_window.book_series_item_widgets:
        if bookWidget.checkboxBtn.isEnabled():
            if not bookWidget.checkboxBtn.isChecked():
                bookWidget.checkboxBtn.click()


def unToggleAll(main_window: MainWindow) -> None:
    for bookWidget in main_window.book_series_item_widgets:
        if bookWidget.checkboxBtn.isEnabled():
            if bookWidget.checkboxBtn.isChecked():
                bookWidget.checkboxBtn.click()


class BookSeriesDownloader(BaseWorker):
    """
    Класс реализующий поиск книг из той же серии.
    """

    finished: QtCore.pyqtBoundSignal = pyqtSignal()  # Поиск завершен
    update_status: QtCore.pyqtBoundSignal = pyqtSignal(object)

    def __init__(self, main_window: MainWindow, books: list[Book], drv: Driver):
        super(BookSeriesDownloader, self).__init__()
        self.main_window = main_window
        self.books = books
        self.drv = drv
        self.launched: list[int] = []
        self.abpd_files: dict[int, str] = {}

    def connectSignals(self) -> None:
        self.finished.connect(lambda: self.finish())
        self.update_status.connect(lambda indexes: self._update_status(indexes))

    def worker(self) -> None:
        logger.opt(colors=True).debug(
            "Preparing to the book series download process: "
            f'<y>"{self.main_window.book.series_name}"</y>'
        )

        json_encoder = msgspec.json.Encoder()
        json_decoder = msgspec.json.Decoder()

        need_downloading_books_indexes = []
        for i, book in enumerate(self.books):
            widget = self.main_window.book_series_item_widgets[i]
            if widget.checkboxBtn.isChecked():
                need_downloading_books_indexes.append(i)
                self.main_window.downloading_book_series_status[book.url] = {
                    "status": DownloadingState.waiting
                }
            widget.checkboxBtn.hide()

        self.update_status.emit(need_downloading_books_indexes)

        abpd_dir = pathlib.Path(os.environ["APP_DIR"], "abpd")
        abpd_dir.mkdir(exist_ok=True)
        for index in need_downloading_books_indexes:
            book = self.books[index]
            info = self.main_window.downloading_book_series_status[book.url]
            self.abpd_files[index] = os.path.join(
                abpd_dir, hashlib.md5(book.url.encode()).hexdigest() + ".abpd"
            )
            with open(self.abpd_files[index], "wb") as file:
                file.write(json_encoder.encode(info))

        logger.opt(colors=True).debug(
            "Starting the book series download process: "
            f'<y>"{self.main_window.book.series_name}"</y>'
        )

        while True:
            if len(need_downloading_books_indexes) == 0:
                break

            updated_indexes: list[int] = []
            for index in need_downloading_books_indexes:
                book = self.books[index]
                abpd_file_path = self.abpd_files[index]
                if not os.path.exists(abpd_file_path):
                    self.main_window.downloading_book_series_status[book.url][
                        "status"
                    ] = DownloadingState.canceled
                    need_downloading_books_indexes.remove(index)
                    updated_indexes.append(index)
                    if index in self.launched:
                        self.launched.remove(index)
                    continue

                try:
                    with open(abpd_file_path, "rb") as file:
                        info = json_decoder.decode(file.read())
                        if "status" not in info:
                            raise
                        info["status"] = DownloadingState(info["status"])
                except Exception as err:
                    logger.opt(colors=True).error(
                        f"Error while reading file <y>{abpd_file_path}</y>. "
                        f"{type(err).__name__}: {str(err)}"
                    )

                if info != self.main_window.downloading_book_series_status[book.url]:
                    self.main_window.downloading_book_series_status[book.url] = info
                    updated_indexes.append(index)
                status = info["status"]

                if status in {DownloadingState.canceled, DownloadingState.done}:
                    os.remove(abpd_file_path)
                    need_downloading_books_indexes.remove(index)
                    if index in self.launched:
                        self.launched.remove(index)
                elif status == DownloadingState.waiting:
                    if index in self.launched:
                        continue
                    if len(self.launched) < 5:
                        subprocess.Popen(
                            [
                                sys.executable,
                                *(
                                    sys.argv[1:]
                                    if sys.argv[0] == sys.executable
                                    else sys.argv
                                ),
                                f"--download-book={book.url}",
                            ]
                        )
                        self.launched.append(index)
                        continue

            if updated_indexes:
                self.update_status.emit(updated_indexes)

            time.sleep(1)

        self.main_window.downloadable_book_series = ...
        self.main_window.downloading_book_series_status.clear()
        self.finished.emit()

    def finish(self) -> None:
        self.main_window.downloadableBookSeriesBtn.hide()
        send_system_notification(
            title="Скачивание книг завершено!",
            message=f'Скачивание книг из цикла "{self.books[0].series_name}" завершено',
        )

    def _update_status(self, books_indexes: list[int]) -> None:
        for book_index in books_indexes:
            if not len(self.main_window.book_series_item_widgets):
                return
            book = self.books[book_index]
            widget = self.main_window.book_series_item_widgets[book_index]
            info = self.main_window.downloading_book_series_status[book.url]

            if not (status := info.get("status")):
                return
            if widget.splitLine.isHidden():
                widget.splitLine.show()
                widget.downloadingFrame.show()

            if status == DownloadingState.downloading:
                if (total_size := info.get("total_size")) is not None and (
                    done_size := info.get("done_size")
                ) is not None:
                    if widget.downloadingProgressBar.isHidden():
                        widget.downloadingProgressBar.show()
                    if widget.stopDownloadingBtn.isHidden():
                        widget.stopDownloadingBtn.show()
                    if not widget.stopDownloadingBtn.isEnabled():
                        widget.stopDownloadingBtn.setDisabled(False)
                    progress = int(round(done_size / (total_size / 100), 0))
                    if progress > widget.downloadingProgressBar.value():
                        widget.downloadingProgressBar.setValue(progress)
                    widget.downloadingStatusLabel.setText(
                        f"{convert_into_bytes(done_size)} / "
                        f"{convert_into_bytes(total_size)}",
                    )
            else:
                widget.downloadingStatusLabel.setText(status.value)
                widget.downloadingProgressBar.hide()
                if status in {
                    DownloadingState.canceled,
                    DownloadingState.done,
                    DownloadingState.preparing,
                }:
                    widget.stopDownloadingBtn.hide()

    def stop_downloading(self, book: Book) -> None:
        index = self.books.index(book)
        try:
            os.remove(self.abpd_files[index])
        except (PermissionError, OSError):
            QTimer.singleShot(100, lambda: self.stop_downloading(book))


def downloadBookSeries(main_window: MainWindow, book_series: list[Book]) -> None:
    if (
        main_window.downloadable_book is not ...
        or main_window.downloadable_book_series is not ...
    ):
        QMessageBox.information(
            main_window,
            "Предупреждение",
            "Дождитесь окончания скачивания другой книги",
        )
        return

    if not any(
        widget.checkboxBtn.isChecked()
        for widget in main_window.book_series_item_widgets
    ):
        QMessageBox.information(
            main_window,
            "Предупреждение",
            "Выберите книги которые хотите скачать",
        )
        return

    main_window.downloadingProgressBar.setValue(0)
    main_window.downloadBookSeriesBtn2.hide()
    main_window.selectAllBooksBtn.hide()
    main_window.unselectAllBooksBtn.hide()
    main_window.downloadable_book_series = book_series

    drv = [drv for drv in drivers if main_window.book.driver == drv.driver_name][0]()

    # Создаем и запускаем новый поток
    main_window.BookSeriesDownloader = BookSeriesDownloader(
        main_window, book_series, drv
    )
    main_window.BookSeriesDownloader.start()


class DownloadProcessHandler(BaseDownloadProcessHandler):
    def __init__(
        self,
        drv: Driver,
        book: Book,
        abpd_file_path: str,
        json_encoder: msgspec.json.Encoder,
    ):
        self.drv = drv
        self.book = book
        self.abpd_file_path = abpd_file_path
        self.json_encoder = json_encoder
        super().__init__()

    def show_progress(self) -> None:
        if not os.path.exists(self.abpd_file_path):
            self.terminate()
        info = {
            "status": DownloadingState.downloading,
            "done_size": self.done_size,
            "total_size": self.total_size,
        }
        with suppress(Exception):
            save_abpd(self.abpd_file_path, info, json_encoder=self.json_encoder)

    def terminate(self):
        file = self.drv.__dict__.get("_file")
        if file:
            file.close()

        if os.path.isdir(self.book.dir_path):
            for root, dirs, files in os.walk(self.book.dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    with suppress(Exception):
                        os.remove(file_path)
                with suppress(Exception):
                    os.rmdir(root)
            if self.book.series_name:
                series_dir = os.path.dirname(self.book.dir_path)
                with suppress(Exception):
                    os.rmdir(series_dir)
                author_dir = os.path.dirname(series_dir)
                with suppress(Exception):
                    os.rmdir(author_dir)
            else:
                author_dir = os.path.dirname(self.book.dir_path)
                with suppress(Exception):
                    os.rmdir(author_dir)
            logger.debug(f"Audio files deleted: {self.book.url}")

        sys.exit()


def download_book(url: str) -> None:
    logger.debug(f"Preparing to downloading book {url}")
    abpd_file_path = os.path.join(
        os.environ["APP_DIR"], "abpd", hashlib.md5(url.encode()).hexdigest() + ".abpd"
    )
    info = load_abpd(abpd_file_path)
    info["status"] = DownloadingState.preparing
    json_encoder = msgspec.json.Encoder()
    save_abpd(abpd_file_path, info, json_encoder=json_encoder)

    drv = [drv for drv in drivers if url.startswith(drv.site_url)][0]()
    logger.debug(f"Getting book data: {url}")
    book = drv.get_book(url)
    drv.quit_browser()
    logger.debug(f"Starting the book download process: {book.url}")
    proc_handler = DownloadProcessHandler(drv, book, abpd_file_path, json_encoder)
    files = drv.download_book(book, proc_handler)
    logger.debug(f"Audio files downloaded {book.url}")
    books = Books(os.environ["DB_PATH"])
    books.insert(
        **vars(book),
        files=BookFiles({file.name: get_file_hash(file) for file in files}),
        file_path=os.path.join(book.dir_path, ".abp"),
        adding_date=DateTime.now(),
    )  # Добавляем книгу в бд
    book = books.filter(url=book.url)
    book.save_to_storage()
    logger.opt(colors=True).debug(f"Start downloading cover for book {book.url}")
    context = ssl.SSLContext()
    cover = urllib.request.urlopen(book.preview, context=context).read()
    with open(os.path.join(book.dir_path, "cover.jpg"), "wb") as cover_file:
        cover_file.write(cover)
    info["status"] = DownloadingState.done
    save_abpd(abpd_file_path, info, json_encoder=json_encoder)
    send_system_notification(
        title="Скачивание книги завершено!",
        message=f'Книга "{book.author} - {book.name}" скачана',
    )


def save_abpd(
    file_path: str, data: dict, json_encoder: msgspec.json.Encoder | None = None
) -> None:
    logger.trace(f"saving {file_path} abpd: {data}")
    if not json_encoder:
        json_encoder = msgspec.json.Encoder()
    with open(file_path, "wb") as file:
        file.write(json_encoder.encode(data))


def load_abpd(file_path: str, json_decoder: msgspec.json.Decoder | None = None) -> dict:
    if not json_decoder:
        json_decoder = msgspec.json.Decoder()
    with open(file_path, "rb") as file:
        return json_decoder.decode(file.read())

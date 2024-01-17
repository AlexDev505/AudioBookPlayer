from __future__ import annotations

import os
import typing as ty
from datetime import datetime

import requests.exceptions
from loguru import logger

from database import Database
from drivers import Driver, BaseDownloadProcessHandler, DownloadProcessStatus
from models.book import DATETIME_FORMAT
from tools import convert_from_bytes, make_book_preview
from .js_api import JSApi, JSApiError


if ty.TYPE_CHECKING:
    from models.book import Book


class BooksApi(JSApi):
    _download_processes: dict[int, Driver] = {}
    _download_queue: list[int] = []

    def get_available_drivers(self):
        return self.make_answer([driver.driver_name for driver in Driver.drivers])

    def book_by_bid(self, bid: int):
        with Database() as db:
            if book := db.get_book_by_bid(bid):
                return self.make_answer(self._answer_book(book))
        return self.error(BookNotFound(bid=bid))

    def get_library(
        self,
        limit: int,
        offset: int = 0,
        sort: str | None = None,
        reverse: bool | None = None,
        author: str | None = None,
        series: str | None = None,
        favorite: bool | None = None,
        status: str | None = None,
    ):
        sort = sort if sort else "adding_date"
        reverse = reverse if reverse is not None else True
        with Database() as db:
            books = db.get_libray(
                limit, offset, sort, reverse, author, series, favorite, status
            )
        return self.make_answer([self._answer_book(book) for book in books])

    def toggle_favorite(self, bid: int):
        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))
            book.favorite = not book.favorite
            db.save(book)
            db.commit()
            return self.make_answer(book.favorite)

    def book_by_url(self, url: str):
        if not (driver := Driver.get_suitable_driver(url)):
            return self.error(NoSuitableDriver(book_url=url))
        try:
            return driver().get_book(url)
        except requests.exceptions.ConnectionError as err:
            return self.error(ConnectionFailedError(err=f"{type(err).__name__}: {err}"))

    def search_books(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        required_drivers: list[str] | None = None,
    ):
        if query.startswith("https://"):
            if isinstance(resp := self.book_by_url(query), JSApiError):
                return resp
            return self.make_answer([make_book_preview(resp)])

        drivers = (
            [
                driver
                for driver in Driver.drivers
                if driver.driver_name in required_drivers
            ]
            if required_drivers
            else Driver.drivers
        )
        if not len(drivers):
            return self.error(NoSuitableDriver())

        result: list[dict] = []
        limit_per_one_driver = limit // len(drivers)
        offset_per_one_driver = offset // len(drivers)
        for driver in drivers:
            driver = driver()
            try:
                books = driver.search_books(
                    query, limit_per_one_driver, offset_per_one_driver
                )
            except AttributeError:
                continue
            result.extend(make_book_preview(book) for book in books)
        return self.make_answer(result)

    def add_book_to_library(self, url: str):
        if isinstance(book := self.book_by_url(url), JSApiError):
            return book
        with Database(autocommit=True) as db:
            if db.check_is_books_exists([url]):
                return self.error(BookAlreadyAdded())
            book.adding_date = datetime.now()
            db.add_book(book)
        return self.make_answer()

    def check_is_books_exists(self, urls: list[str]):
        with Database() as db:
            return self.make_answer(db.check_is_books_exists(urls))

    def get_downloads(self):
        downloads: list[tuple[int, str, str | None, str | None]] = []
        with Database() as db:
            for bid in [*self._download_processes.keys(), *self._download_queue]:
                book = db.get_book_by_bid(bid)
                status = DownloadProcessStatus.WAITING.value
                total_size = None
                if bid in self._download_processes:
                    downloader = self._download_processes[bid].downloader
                    status = downloader.process_handler.status.value
                    total_size = (
                        convert_from_bytes(downloader.process_handler.total_size)
                        if downloader.process_handler.status
                        == DownloadProcessStatus.DOWNLOADING
                        else str(downloader.process_handler.total_size)
                    )
                downloads.append((bid, book.name, status, total_size))
        return downloads

    def download_book(self, bid: int):
        if bid in self._download_processes:
            return self.error(BookAlreadyDownloaded(bid=bid))

        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))

        if len(self._download_processes) >= 5:
            self._download_queue.append(bid)
            logger.opt(colors=True).debug(f"{book} added to download queue")
            return self.make_answer(dict(bid=bid))

        driver = Driver.get_suitable_driver(book.url)()
        self._download_processes[bid] = driver
        if driver.download_book(book, DownloadingProcessHandler(self, bid)):
            logger.opt(colors=True).debug(f"saving {book} into db")
            with Database(autocommit=True) as db:
                db.save(driver.downloader.book)
        del self._download_processes[bid]

        if self._download_queue:
            self.download_book(self._download_queue.pop(0))

    def terminate_downloading(self, bid: int):
        if bid in self._download_queue:
            self._download_queue.remove(bid)
        elif download_process := self._download_processes.get(bid):
            download_process.downloader.terminate()

    def delete_book(self, bid: int):
        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))

        if not book.files:
            return self.error(BookNotDownloaded(bid=bid))

        for file in book.files.keys():
            file_path = os.path.join(book.dir_path, file)
            try:
                os.remove(file_path)
            except PermissionError:
                logger.error(f"File locked. {file_path}")
            except IOError as err:
                logger.exception(err)

        book.files.clear()
        with Database(autocommit=True) as db:
            db.save(book)

        return self.make_answer()

    def remove_book(self, bid: int):
        # TODO: если книга скачана, помечать книгу как исключенную
        #  (можно добавлять это в .abp и не добавлять книгу в бд при запуске)
        with Database() as db:
            if not (db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))

            db.remove_book(bid)
            db.commit()

        return self.make_answer()

    def _answer_book(self, book: Book) -> dict:
        return dict(
            bid=book.id,
            author=book.author,
            name=book.name,
            series_name=book.series_name,
            number_in_series=book.number_in_series,
            description=book.description,
            reader=book.reader,
            duration=book.duration,
            preview=book.preview,
            driver=book.driver,
            status=book.status.value,
            listening_progress=book.listening_progress,
            favorite=book.favorite,
            adding_date=book.adding_date.strftime(DATETIME_FORMAT),
            downloaded=bool(len(book.files)),
            downloading=(
                book.id in self._download_queue or book.id in self._download_processes
            ),
        )


class DownloadingProcessHandler(BaseDownloadProcessHandler):
    def __init__(self, js_api: JSApi, bid: int):
        self.js_api = js_api
        self.bid = bid
        super().__init__()

    def init(self, total_size: int, status: DownloadProcessStatus) -> None:
        super().init(total_size, status)
        total_size = (
            convert_from_bytes(total_size)
            if status == DownloadProcessStatus.DOWNLOADING
            else total_size
        )
        self.js_api.evaluate_js(f"initTotalSize({self.bid}, '{total_size}')")

    def show_progress(self) -> None:
        done_size = (
            convert_from_bytes(self.done_size)
            if self.status == DownloadProcessStatus.DOWNLOADING
            else self.done_size
        )
        self.js_api.evaluate_js(
            f"downloadingCallback({self.bid}, "
            f"{round(self.done_size / (self.total_size / 100), 2)}, '{done_size}')"
        )

    @property
    def status(self) -> DownloadProcessStatus:
        return self._status

    @status.setter
    def status(self, v: DownloadProcessStatus):
        self._status = v
        self.js_api.evaluate_js(f"setDownloadingStatus({self.bid}, '{v.value}')")


class ConnectionFailedError(JSApiError):
    code = 1
    message = "Ошибка соединения"


class NoSuitableDriver(JSApiError):
    code = 2
    message = "Нет подходящего драйвера"


class BookAlreadyAdded(JSApiError):
    code = 3
    message = "Книга уже добавлена в библиотеку"


class BookNotFound(JSApiError):
    code = 4
    message = "Книга не найдена"


class BookAlreadyDownloaded(JSApiError):
    code = 5
    message = "Книга скачивается или уже скачана"


class BookNotDownloaded(JSApiError):
    code = 6
    message = "Книга не скачана"

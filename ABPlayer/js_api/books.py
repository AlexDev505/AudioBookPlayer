from __future__ import annotations

import difflib
import os
import typing as ty
from dataclasses import asdict
from datetime import datetime
from functools import partial

import requests.exceptions
from loguru import logger

from database import Database
from drivers import Driver, BaseDownloadProcessHandler, DownloadProcessStatus
from models.book import DATETIME_FORMAT
from tools import convert_from_bytes, make_book_preview, pretty_view
from .js_api import JSApi, JSApiError, ConnectionFailedError


if ty.TYPE_CHECKING:
    from models.book import Book


class BooksApi(JSApi):
    _download_processes: dict[int, Driver] = {}
    _download_queue: list[int] = []

    def __init__(self):
        self.search_query: str | None = None
        self.matched_books_bids: list[int] | None = None
        self.removed_books_files: dict[int, tuple[str, list[str]]] = {}

    def get_available_drivers(self):
        logger.opt(colors=True).debug("request: <r>available drivers</r>")
        available_drivers = [driver.driver_name for driver in Driver.drivers]
        logger.opt(colors=True).debug(
            f"available drivers count: <y>{len(available_drivers)}</y>"
        )
        return self.make_answer(available_drivers)

    def book_by_bid(self, bid: int, listening_data: bool = False):
        logger.opt(colors=True).debug(f"request: <r>book by bid</r> | <y>{bid}</y>")
        with Database() as db:
            if book := db.get_book_by_bid(bid):
                logger.opt(colors=True).debug(f"book found: {book:styled}")
                return self.make_answer(self._answer_book(book, listening_data))
        logger.opt(colors=True).error(f"book not found. bid=<y>{bid}</y>")
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
        search_query: str | None = None,
    ):
        logger.opt(colors=True).debug("request: <r>library</r>")
        sort = sort if sort else "adding_date"
        reverse = not reverse if reverse is not None else True
        if search_query is not None and search_query != self.search_query:
            self.search_in_library(search_query)
        if search_query is None and self.search_query is not None:
            self.search_query = None
            self.matched_books_bids = None
        bids = self.matched_books_bids

        logger.opt(lazy=True).trace(
            "library filters: {data}",
            data=partial(
                pretty_view,
                dict(
                    limit=limit,
                    offset=offset,
                    sort=sort,
                    reverse=reverse,
                    author=author,
                    series=series,
                    favorite=favorite,
                    status=status,
                    bids=bids,
                ),
            ),
        )

        with Database() as db:
            books = db.get_libray(
                limit, offset, sort, reverse, author, series, favorite, status, bids
            )

        logger.opt(colors=True).debug(
            f"<y>{len(books)}</y> books found. "
            f"bids: {pretty_view([book.id for book in books])}"
        )

        return self.make_answer([self._answer_book(book) for book in books])

    def search_in_library(self, query: str):
        logger.opt(colors=True).debug(
            f"request: <r>search in library</r> | <y>{query}</y>"
        )
        self.search_query = query
        with Database() as db:
            search_array = db.get_books_keywords()
            logger.opt(colors=True).trace(f"search array: {search_array}")
            search_words = query.lower().split()
            logger.opt(colors=True).trace(f"search words: {search_words}")
            matched_books_bids = []  # Идентификаторы найденных книг
            # Поиск
            for i, array in search_array.items():
                for search_word in search_words:
                    if difflib.get_close_matches(search_word, array):
                        matched_books_bids.append(i)
                        break
            logger.opt(colors=True).debug(
                f"matched books bids: {pretty_view(matched_books_bids)}"
            )
            self.matched_books_bids = matched_books_bids

    def get_all_authors(self):
        logger.opt(colors=True).debug("request: <r>all authors</r>")
        with Database() as db:
            authors = db.get_all_authors()
        logger.opt(colors=True).debug(f"authors found: <y>{len(authors)}</y>")
        return self.make_answer(authors)

    def get_all_series(self):
        logger.opt(colors=True).debug("request: <r>all series</r>")
        with Database() as db:
            series = db.get_all_series()
        logger.opt(colors=True).debug(f"series found: <y>{len(series)}</y>")
        return self.make_answer(series)

    def toggle_favorite(self, bid: int):
        logger.opt(colors=True).debug(f"request: <r>toggle favorite</r> | <y>{bid}</y>")
        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))
            book.favorite = not book.favorite
            db.save(book)
            db.commit()
            logger.opt(colors=True).debug(
                f"{book:styled} favorite: <y>{book.favorite}</y>"
            )
            return self.make_answer(book.favorite)

    @staticmethod
    def _book_by_url(url: str):
        logger.opt(colors=True).debug(
            f"request: <r>search book by url</r> | <y>{url}</y>"
        )
        if not (driver := Driver.get_suitable_driver(url)):
            return NoSuitableDriver(book_url=url)
        try:
            book = driver().get_book(url)
            logger.opt(colors=True).debug(f"book found: {book:styled}")
            return book
        except requests.exceptions.ConnectionError as err:
            return ConnectionFailedError(err=f"{type(err).__name__}: {err}")

    def search_books(
        self,
        query: str,
        limit: int = 10,
        offset: int = 0,
        required_drivers: list[str] | None = None,
    ):
        logger.opt(colors=True).debug(f"request: <r>search books</r> | <y>{query}</y>")
        if query.startswith("https://"):
            if isinstance(resp := self._book_by_url(query), JSApiError):
                return self.error(resp)
            print([resp])
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

        logger.opt(lazy=True).trace(
            "search params: {data}",
            data=partial(
                pretty_view,
                dict(
                    query=query,
                    limit=limit,
                    offset=offset,
                    required_drivers=required_drivers,
                ),
            ),
        )

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
            except requests.exceptions.RequestException as err:
                return self.error(
                    ConnectionFailedError(err=f"{type(err).__name__}: {err}")
                )
            result.extend(make_book_preview(book) for book in books)

        logger.opt(colors=True).debug(
            f"<y>{len(result)}</y> books found. "
            f"urls: {pretty_view([book['url'] for book in result])}"
        )

        return self.make_answer(result)

    def add_book_to_library(self, url: str):
        logger.opt(colors=True).debug(
            f"request: <r>add book to library</r> | <y>{url}</y>"
        )
        if isinstance(book := self._book_by_url(url), JSApiError):
            return self.error(book)
        with Database(autocommit=True) as db:
            if db.check_is_books_exists([url]):
                return self.error(BookAlreadyAdded())
            book.adding_date = datetime.now()
            db.add_book(book)

        logger.opt(colors=True).debug(f"book added to library: {book:styled}")
        logger.opt(lazy=True).trace(
            "book: {data}",
            data=partial(
                pretty_view,
                book.to_dump(),
                multiline=not os.getenv("NO_MULTILINE", False),
            ),
        )

        return self.make_answer()

    def check_is_books_exists(self, urls: list[str]):
        logger.opt(colors=True).debug("request: <r>check is books exists</r>")
        with Database() as db:
            exists_book_urls = db.check_is_books_exists(urls)
        logger.opt(colors=True).debug(
            f"<y>{len(exists_book_urls)}/{len(urls)}</y> books exists"
        )
        return self.make_answer(exists_book_urls)

    def get_downloads(self):
        logger.opt(colors=True).debug("request: <r>get downloads</r>")
        downloads: list[tuple[int, str, str | None, str | None]] = []
        # [(bid, book_name, status, total_size), ...]
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

        logger.opt(colors=True).debug(
            f"<y>{len(downloads)}</y> downloads found."
            f"bids: {pretty_view([process[0] for process in downloads])}"
        )

        return self.make_answer(downloads)

    def download_book(self, bid: int):
        logger.opt(colors=True).debug(f"request: <r>download book</r> | <y>{bid}</y>")
        if bid in self._download_processes:
            return self.error(BookAlreadyDownloaded(bid=bid))

        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))

        if len(self._download_processes) >= 5:
            self._download_queue.append(bid)
            logger.opt(colors=True).debug(f"added to download queue: {book:styled}")
            return self.make_answer(dict(bid=bid))

        logger.opt(colors=True).debug(f"preparing download: {book:styled}")
        driver = Driver.get_suitable_driver(book.url)()
        self._download_processes[bid] = driver
        if driver.download_book(book, DownloadingProcessHandler(self, bid)):
            logger.opt(colors=True).debug(f"saving into db: {book:styled}")
            with Database(autocommit=True) as db:
                db.save(driver.downloader.book)
            self.evaluate_js(f"endLoading({bid})")
            logger.opt(colors=True).info(f"downloading finished: {book:styled}")

        del self._download_processes[bid]

        if self._download_queue:
            self.download_book(self._download_queue.pop(0))

        return self.make_answer()

    def terminate_downloading(self, bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>terminate downloading</r> | <y>{bid}</y>"
        )
        if bid in self._download_queue:
            self._download_queue.remove(bid)
        elif download_process := self._download_processes.get(bid):
            download_process.downloader.terminate()
        logger.opt(colors=True).debug(f"downloading of book <y>{bid}</y> terminated")

    @staticmethod
    def _delete_book_files(dir_path: str, files: list[str]) -> None:
        for file in [*files, "cover.jpg", ".abp"]:
            file_path = os.path.join(dir_path, file)
            try:
                logger.opt(colors=True).trace(f"deleting <y>{file_path}</y>")
                os.remove(file_path)
            except PermissionError:
                logger.error(f"file locked. {file_path}")
            except IOError as err:
                logger.exception(err)

        os.removedirs(dir_path)

    def delete_book(self, bid: int):
        logger.opt(colors=True).debug(f"request: <r>delete book</r> | <y>{bid}</y>")
        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                if bid in self.removed_books_files:
                    logger.debug("deleting residual book files")
                    self._delete_book_files(*self.removed_books_files[bid])
                    del self.removed_books_files[bid]
                    logger.opt(colors=True).info(f"book deleted: <y>{bid}</y>")
                    return self.make_answer()
                return self.error(BookNotFound(bid=bid))

        if not book.files:
            return self.error(BookNotDownloaded(bid=bid))

        logger.opt(colors=True).debug(f"deleting book: {book:styled}")
        self._delete_book_files(book.dir_path, list(book.files.keys()))
        os.remove(book.abp_file_path)

        logger.opt(colors=True).debug(f"clearing files data from db: {book:styled}")
        book.files.clear()
        with Database(autocommit=True) as db:
            db.save(book)

        logger.opt(colors=True).info(f"book deleted: {book:styled}")
        return self.make_answer()

    def remove_book(self, bid: int):
        logger.opt(colors=True).debug(f"request: <r>remove book</r> | <y>{bid}</y>")
        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))

            if book.files:
                self.removed_books_files[bid] = (book.dir_path, list(book.files.keys()))
                os.remove(book.abp_file_path)
            db.remove_book(bid)
            db.commit()

        logger.opt(colors=True).info(f"book removed: <y>{book:styled}</y>")
        return self.make_answer()

    def _answer_book(self, book: Book, listening_data: bool = False) -> dict:
        data = dict(
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
        if listening_data:
            book_path = book.book_path
            data.update(
                dict(
                    stop_flag=asdict(book.stop_flag),
                    items=book.items.to_dump(),
                    files=[
                        os.path.join(book_path, file_name) for file_name in book.files
                    ],
                )
            )
        return data


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

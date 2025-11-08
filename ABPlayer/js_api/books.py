from __future__ import annotations

import difflib
import os
import shutil
import time
import typing as ty
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime
from functools import partial
from pathlib import Path

import requests.exceptions
from database import Database
from drivers import BaseDownloadProcessHandler, DownloadProcessStatus, Driver
from drivers import download as download_book
from drivers import terminate as terminate_downloading
from drivers.base import DriverNotAuthenticated, LicensedDriver
from drivers.tools import duration_sec_to_str, duration_str_to_sec
from loguru import logger
from models.book import DATETIME_FORMAT, Status, StopFlag
from tools import convert_from_bytes, make_book_preview, pretty_view

from .js_api import ConnectionFailedError, JSApi, JSApiError

if ty.TYPE_CHECKING:
    from models.book import Book


class BooksApi(JSApi):
    SEARCH_LIMIT = 10
    _download_processes: dict[int, DownloadingProcessHandler | None] = {}
    _download_queue: list[int] = []

    def __init__(self):
        self.library_search_query: str | None = None
        self.matched_books_bids: list[int] | None = None
        self.removed_books_files: dict[int, tuple[str, list[str]]] = {}
        self.search_state: dict[str, [int, bool]] = {}
        # {<driver name>: [<search offset>, <can load next>]}

    def book_by_bid(self, bid: int, listening_data: bool = False):
        logger.opt(colors=True).debug(
            f"request: <r>book by bid</r> | <y>{bid}</y>"
        )
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
        if (
            search_query is not None
            and search_query != self.library_search_query
        ):
            self.search_in_library(search_query)
        if search_query is None and self.library_search_query is not None:
            self.library_search_query = None
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
                limit,
                offset,
                sort,
                reverse,
                author,
                series,
                favorite,
                status,
                bids,
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
        self.library_search_query = query
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

    def _book_by_url(self, url: str):
        logger.opt(colors=True).debug(
            f"request: <r>search book by url</r> | <y>{url}</y>"
        )
        if not (driver := Driver.get_suitable_driver(url)):
            return NoSuitableDriver(book_url=url)
        try:
            book = driver().get_book(url)
            logger.opt(colors=True).debug(f"book found: {book:styled}")
            return book
        except (AttributeError, KeyError, ValueError) as err:
            logger.opt().error(
                f"getting book ({url}) raises {type(err).__name__}: {err}"
            )
            logger.exception(err)
        except DriverNotAuthenticated:
            self.logout_driver(driver.driver_name)
            return NotAuthenticated()
        except requests.exceptions.ConnectionError as err:
            return ConnectionFailedError(err=f"{type(err).__name__}: {err}")

    def search_books(
        self,
        query: str,
        required_drivers: list[str] | None = None,
    ):
        if query.startswith("https://"):
            if isinstance(resp := self._book_by_url(query), JSApiError):
                return self.error(resp)
            return self.make_answer([make_book_preview(resp)] if resp else [])

        if required_drivers is not None:
            self.search_state = {
                driver_name: [0, True] for driver_name in required_drivers
            }
            logger.opt(colors=True).debug(
                f"request: <r>search books</r> | <y>{query}</y>"
            )
        else:
            logger.opt(colors=True).debug(
                f"request: <r>search more books</r> | <y>{self.search_state}</y>"
            )

        drivers = [
            driver
            for driver in Driver.drivers
            if driver.driver_name in self.search_state
            and self.search_state[driver.driver_name][1]
        ]

        logger.opt(lazy=True).trace(
            "search params: {data}",
            data=partial(
                pretty_view, dict(query=query, states=self.search_state)
            ),
        )

        result: list[dict] = []
        limit_per_one_driver = self.SEARCH_LIMIT // (len(drivers) or 1)
        for driver in drivers:
            driver = driver()
            try:
                books = driver.search_books(
                    query,
                    limit_per_one_driver,
                    self.search_state[driver.driver_name][0],
                )
                self.search_state[driver.driver_name][0] += len(books)
                if len(books) < limit_per_one_driver:
                    self.search_state[driver.driver_name][1] = False
            except (AttributeError, KeyError, ValueError) as err:
                logger.opt().error(
                    f"searching book by {driver.driver_name} driver ({query}) "
                    f"raises {type(err).__name__}: {err}"
                )
                logger.exception(err)
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

    def search_book_series(self, url: str):
        logger.opt(colors=True).debug(
            f"request: <r>search book series</r> | <y>{url}</y>"
        )
        if not (driver := Driver.get_suitable_driver(url)):
            return NoSuitableDriver(book_url=url)
        try:
            result = [
                make_book_preview(book)
                for book in driver().get_book_series(url)
            ]
            logger.opt(colors=True).debug(
                f"<y>{len(result)}</y> books found. "
                f"urls: {pretty_view([book['url'] for book in result])}"
            )
            return self.make_answer(result)
        except (AttributeError, KeyError, ValueError) as err:
            logger.opt().error(
                f"getting book ({url}) raises {type(err).__name__}: {err}"
            )
            logger.exception(err)
            return self.make_answer([])
        except requests.exceptions.ConnectionError as err:
            return self.error(
                ConnectionFailedError(err=f"{type(err).__name__}: {err}")
            )

    def add_book_to_library(self, url: str):
        logger.opt(colors=True).debug(
            f"request: <r>add book to library</r> | <y>{url}</y>"
        )
        if isinstance(book := self._book_by_url(url), JSApiError):
            return self.error(book)
        with Database(autocommit=True) as db:
            if db.check_is_books_exists([url]):
                return self.error(BookAlreadyAdded())
            if exists_book := db.mark_multi_readers(book):
                if exists_book.id in self._download_processes:
                    return self.error(WaitForDownloadingEnd())
                logger.opt(colors=True).debug(
                    f"{book:styled} marked as multi_reader with {exists_book:styled}"
                )
                if exists_book.files:
                    self._move_multi_reader_book(exists_book)
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

    def toggle_favorite(self, bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>toggle favorite</r> | <y>{bid}</y>"
        )
        with Database(autocommit=True) as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))
            book.favorite = not book.favorite
            db.save(book)
            logger.opt(colors=True).debug(
                f"{book:styled} favorite: <y>{book.favorite}</y>"
            )
            return self.make_answer(book.favorite)

    def mark_as_new(self, bid: int):
        return self._set_book_status(bid, Status.NEW)

    def mark_as_started(self, bid: int):
        return self._set_book_status(bid, Status.STARTED)

    def mark_as_finished(self, bid: int):
        return self._set_book_status(bid, Status.FINISHED)

    def _set_book_status(self, bid: int, status: Status):
        logger.opt(colors=True).debug(
            f"request: <r>set book status</r> | <y>{bid}</y>"
        )
        with Database(autocommit=True) as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))
            book.status = status
            if status == Status.NEW:
                book.stop_flag = StopFlag()
            db.save(book)
            logger.opt(colors=True).debug(
                f"{book:styled} status: <y>{book.status.value}</y>"
            )
            return self.make_answer()

    def set_stop_flag(self, bid: int, item: int, time: int):
        logger.opt(colors=True).trace(
            f"request: <r>set stop flag</r> | <y>{bid}</y>"
        )
        with Database(autocommit=True) as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))
            book.stop_flag.item = item
            book.stop_flag.time = time
            db.save(book)

    def get_all_authors(self):
        logger.opt(colors=True).debug("request: <r>all authors</r>")
        with Database() as db:
            authors = db.get_all_authors()
        authors.sort()
        logger.opt(colors=True).debug(f"authors found: <y>{len(authors)}</y>")
        return self.make_answer(authors)

    def get_all_series(self):
        logger.opt(colors=True).debug("request: <r>all series</r>")
        with Database() as db:
            series = db.get_all_series()
        series.sort()
        logger.opt(colors=True).debug(f"series found: <y>{len(series)}</y>")
        return self.make_answer(series)

    def get_series_duration(self, series_name: str):
        logger.opt(colors=True).debug("request: <r>all series</r>")
        with Database() as db:
            durations = db.get_series_durations(series_name)
        total_duration = 0
        for duration in durations:
            with suppress(ValueError):
                total_duration += duration_str_to_sec(duration)
        return self.make_answer(duration_sec_to_str(total_duration))

    def check_is_books_exists(self, urls: list[str]):
        logger.opt(colors=True).debug("request: <r>check is books exists</r>")
        with Database() as db:
            exists_book_urls = db.check_is_books_exists(urls)
        logger.opt(colors=True).debug(
            f"<y>{len(exists_book_urls)}/{len(urls)}</y> books exists"
        )
        return self.make_answer(exists_book_urls)

    def get_available_drivers(self):
        logger.opt(colors=True).debug("request: <r>available drivers</r>")
        available_drivers = [
            dict(
                name=driver.driver_name,
                licensed=issubclass(driver, LicensedDriver),
                authed=getattr(driver, "is_authed", True),
                url=driver.site_url,
            )
            for driver in Driver.drivers
        ]
        logger.opt(colors=True).debug(
            f"available drivers count: <y>{len(available_drivers)}</y>"
        )
        return self.make_answer(available_drivers)

    def logout_driver(self, driver_name: str):
        logger.opt(colors=True).debug(
            f"request: <r>logout driver</r> | <y>{driver_name}</y>"
        )
        driver = next(
            (
                driver
                for driver in Driver.drivers
                if driver.driver_name == driver_name
            ),
            None,
        )
        if not driver or not issubclass(driver, LicensedDriver):
            return self.error(NoSuitableDriver())
        driver.logout()
        logger.opt(colors=True).debug(f"Logout from <y>{driver}</y>")
        return self.make_answer()

    def login_driver(self, driver_name: str):
        logger.opt(colors=True).debug(
            f"request: <r>login driver</r> | <y>{driver_name}</y>"
        )
        driver = next(
            (
                driver
                for driver in Driver.drivers
                if driver.driver_name == driver_name
            ),
            None,
        )
        if not driver or not issubclass(driver, LicensedDriver):
            return self.error(NoSuitableDriver())
        if not driver.auth():
            return self.error(NotAuthenticated())
        logger.opt(colors=True).debug(f"Login to <y>{driver}</y>")
        return self.make_answer()

    def get_downloads(self):
        logger.opt(colors=True).debug("request: <r>get downloads</r>")
        downloads: list[tuple[int, str, str | None, str | None]] = []
        # [(bid, book_name, status, total_size), ...]
        with Database() as db:
            for bid in [
                *self._download_processes.keys(),
                *self._download_queue,
            ]:
                book = db.get_book_by_bid(bid)
                status = DownloadProcessStatus.WAITING.value
                total_size = None
                if dph := self._download_processes.get(bid):
                    status = dph.status.value
                    total_size = (
                        convert_from_bytes(dph.total_size)
                        if dph.status == DownloadProcessStatus.DOWNLOADING
                        else str(dph.total_size)
                    )
                downloads.append((bid, book.name, status, total_size))

        logger.opt(colors=True).debug(
            f"<y>{len(downloads)}</y> downloads found."
            f"bids: {pretty_view([process[0] for process in downloads])}"
        )

        return self.make_answer(downloads)

    def download_book(self, bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>download book</r> | <y>{bid}</y>"
        )
        if self._download_processes.get(bid):
            return self.error(BookAlreadyDownloaded(bid=bid))
        self._download_processes[bid] = None

        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))

        try:
            resp = requests.head(book.items[0].file_url)
            if resp.status_code == 410:
                self.fix_items(bid)
        except requests.exceptions.ConnectionError:
            return self.error(ConnectionFailedError())

        if len([1 for x in self._download_processes.values() if x]) >= 5:
            self._download_queue.append(bid)
            logger.opt(colors=True).debug(
                f"added to download queue: {book:styled}"
            )
            return self.make_answer(dict(bid=bid))

        logger.opt(colors=True).debug(f"preparing download: {book:styled}")
        dph = DownloadingProcessHandler(self, bid)
        self._download_processes[bid] = dph
        download_book(bid, dph)

        return self.make_answer()

    def _finish_download(self, bid: int):
        dph = self._download_processes.pop(bid)
        if dph.status is DownloadProcessStatus.FINISHED:
            self.evaluate_js(f"endLoading({bid})")
            logger.opt(colors=True).info(f"downloading finished: <y>{bid}</y>")
        elif dph.status is DownloadProcessStatus.TERMINATED:
            logger.opt(colors=True).debug(
                f"downloading of book <y>{bid}</y> terminated"
            )

        if self._download_queue:
            self.download_book(self._download_queue.pop(0))

    def terminate_downloading(self, bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>terminate downloading</r> | <y>{bid}</y>"
        )
        if bid in self._download_queue:
            self._download_queue.remove(bid)
            if bid in self._download_processes:
                self._download_processes.pop(bid)
        elif bid in self._download_processes:
            dph = self._download_processes[bid]
            while dph is None:
                dph = self._download_processes.get(bid)
            terminate_downloading(bid)
        return self.make_answer()

    @staticmethod
    def _delete_book_files(dir_path: str, files: list[str]) -> None:
        for file in files:
            file_path = os.path.join(dir_path, file)
            try:
                logger.opt(colors=True).trace(f"deleting <y>{file_path}</y>")
                os.remove(file_path)
            except PermissionError:
                logger.error(f"file locked. {file_path}")
            except IOError as err:
                logger.exception(err)

        os.removedirs(dir_path)

    def _move_multi_reader_book(self, book: Book, _retry: bool = False):
        logger.opt(colors=True).debug(
            f"request: <r>move_multi_reader_book</r> | {book:styled}"
        )
        new_path = book.dir_path
        book.multi_readers = False
        old_path = book.dir_path
        Path(new_path).mkdir(parents=True, exist_ok=True)

        for file in [*book.files, "cover.jpg", ".abp"]:
            file_path = os.path.join(old_path, file)
            dst = os.path.join(new_path, file)
            try:
                logger.opt(colors=True).trace(
                    f"moving <y>{file_path}</y> to <y>{dst}</y>"
                )
                shutil.move(file_path, dst)
            except PermissionError:
                logger.error(f"file locked. {file_path}")
                self.evaluate_js("clearPlayingBook()")
                if not _retry:
                    logger.debug("retrying move_multi_reader_book")
                    return self._move_multi_reader_book(book, True)
            except Exception as err:
                logger.exception(f"moving file {file_path} failed: {err}")

    def delete_book(self, bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>delete book</r> | <y>{bid}</y>"
        )
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
        self._delete_book_files(
            book.dir_path, [*book.files.keys(), "cover.jpg", ".abp"]
        )

        logger.opt(colors=True).debug(
            f"clearing files data from db: {book:styled}"
        )
        book.files.clear()
        with Database(autocommit=True) as db:
            db.save(book)

        logger.opt(colors=True).info(f"book deleted: {book:styled}")
        return self.make_answer()

    def remove_book(self, bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>remove book</r> | <y>{bid}</y>"
        )
        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))

            if book.files:
                self.removed_books_files[bid] = (
                    book.dir_path,
                    [*book.files.keys(), "cover.jpg"],
                )
                os.remove(book.abp_file_path)
            db.remove_book(bid)
            db.commit()

        logger.opt(colors=True).info(f"book removed: <y>{book:styled}</y>")
        return self.make_answer()

    @staticmethod
    def fix_preview(bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>fix preview</r> | <y>{bid}</y>"
        )
        with Database(autocommit=True) as db:
            if not (book := db.get_book_by_bid(bid)):
                return
            driver = Driver.get_suitable_driver(book.url)()
            try:
                new_data = driver.get_book(book.url)
            except requests.exceptions.ConnectionError as err:
                return
            book.preview = new_data.preview
            logger.opt(colors=True).info(
                f"new book <y>{bid}</y> preview: {book.preview}"
            )
            db.save(book)

    @staticmethod
    def fix_items(bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>fix items</r> | <y>{bid}</y>"
        )
        with Database(autocommit=True) as db:
            if not (book := db.get_book_by_bid(bid)):
                return
            driver = Driver.get_suitable_driver(book.url)()
            new_data = driver.get_book(book.url)
            book.items = new_data.items
            logger.opt(colors=True).info(f"book <y>{bid}</y> items are fixed")
            db.save(book)

    def open_book_dir(self, bid: int):
        logger.opt(colors=True).debug(
            f"request: <r>open book dir</r> | <y>{bid}</y>"
        )
        with Database() as db:
            if not (book := db.get_book_by_bid(bid)):
                return self.error(BookNotFound(bid=bid))
        if not os.path.exists(book.dir_path):
            return self.error(BookNotDownloaded(bid=bid))
        os.startfile(book.dir_path)
        return self.make_answer()

    def _answer_book(self, book: Book, listening_data: bool = False) -> dict:
        data = dict(
            bid=book.id,
            author=book.author,
            name=book.name,
            series_name=book.series_name,
            number_in_series=book.number_in_series,
            url=book.url,
            description=book.description,
            reader=book.reader,
            duration=book.duration,
            preview=book.preview,
            local_preview=os.path.join(book.book_path, "cover.jpg").replace(
                "\\", "/"
            ),
            driver=book.driver,
            status=book.status.value,
            listening_progress=book.listening_progress,
            favorite=book.favorite,
            adding_date=book.adding_date.strftime(DATETIME_FORMAT),
            downloaded=bool(len(book.files)),
            downloading=(
                book.id in self._download_queue
                or book.id in self._download_processes
            ),
        )
        if listening_data:
            book_path = book.book_path
            data.update(
                dict(
                    stop_flag=asdict(book.stop_flag),
                    items=book.items.to_dump(),
                    files=[
                        os.path.join(book_path, file_name)
                        for file_name in book.files
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
        with suppress(Exception):
            self.js_api.evaluate_js(
                f"downloadingCallback({self.bid}, "
                f"{round(self.done_size / (self.total_size / 100), 2)}, '{done_size}')"
            )

    @property
    def status(self) -> DownloadProcessStatus:
        return self._status

    @status.setter
    def status(self, v: DownloadProcessStatus):
        if v is DownloadProcessStatus.FINISHING:
            self.done_size = self.total_size
            self.show_progress()
        self._status = v
        with suppress(Exception):
            self.js_api.evaluate_js(
                f"setDownloadingStatus({self.bid}, '{v.value}')"
            )
        if v in {
            DownloadProcessStatus.FINISHED,
            DownloadProcessStatus.TERMINATED,
        }:
            self.js_api._finish_download(self.bid)


class NoSuitableDriver(JSApiError):
    code = 2
    message = _("no_suitable_driver")


class BookAlreadyAdded(JSApiError):
    code = 3
    message = _("book.already_exists")


class BookNotFound(JSApiError):
    code = 4
    message = _("book.not_found")


class BookAlreadyDownloaded(JSApiError):
    code = 5
    message = _("book.already_downloaded")


class BookNotDownloaded(JSApiError):
    code = 6
    message = _("book.not_downloaded")


class WaitForDownloadingEnd(JSApiError):
    code = 9
    message = _("book.wait_for_similar_book_downloading")


class NotAuthenticated(JSApiError):
    code = 10
    message = _("driver.not_authenticated")

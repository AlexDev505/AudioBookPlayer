from __future__ import annotations

from contextlib import suppress

from loguru import logger

import drivers
from database import Database
from models.book import BookStatus, SourceId
from tools import convert_from_bytes, pretty_view

from .exceptions import NotFound
from .js_api import JSApi


class LibraryApi(JSApi):
    def __init__(self):
        super().__init__()

        self._library_search_query: str | None = None
        self._matched_books_bids: list[int] | None = None

    def book_by_bid(self, bid: int, listening_data: bool = True):
        if book := Database().get_book_by_bid(bid, with_sources=listening_data):
            logger.opt(colors=True).debug(f"book found: {book:styled}")
            return book.asdict(with_sources=listening_data)
        raise NotFound(bid=bid)

    def get_library(
        self,
        limit: int,
        offset: int = 0,
        sort: str = "adding_date",
        reverse: bool = False,
        author: str | None = None,
        series: str | None = None,
        favorite: bool | None = None,
        status: str | None = None,
        search_query: str | None = None,
    ):
        if (
            search_query is not None
            and search_query != self._library_search_query
        ):
            self.search_in_library(search_query)
        if search_query is None and self._library_search_query is not None:
            self._library_search_query = None
            self._matched_books_bids = None

        books = Database().get_library(
            limit=limit,
            offset=offset,
            sort=sort,
            reverse=reverse,
            author=author,
            series=series,
            favorite=favorite,
            status=BookStatus(status) if status else None,
            bids=self._matched_books_bids,
        )

        logger.opt(colors=True).debug(
            f"<y>{len(books)}</y> books found. "
            f"bids: {pretty_view([book.id for book in books])}"
        )

        return [book.asdict() for book in books]

    @SourceId.convert_param
    def select_source(self, sid: SourceId):
        Database().select_source(sid)

    @SourceId.convert_param
    def mark_audio_book_as_in_progress(self, sid: SourceId):
        Database().mark_as_in_progress(sid)

    @SourceId.convert_param
    def mark_audio_book_as_completed(self, sid: SourceId):
        Database().mark_as_completed(sid)

    @SourceId.convert_param
    def set_listening_progress(
        self, sid: SourceId, chapter_index: int, progress: int
    ):
        Database().set_listening_progress(
            sid, int(chapter_index), int(progress)
        )

    @SourceId.convert_param
    def set_reading_progress(self, sid: SourceId, cfi: str, percent: int):
        Database().set_reading_progress(sid, cfi, percent)

    @SourceId.convert_param
    def download_book(self, sid: SourceId):
        drivers.download(sid, DownloadingProcessHandler(self, sid))

    @SourceId.convert_param
    def terminate_download(self, sid: SourceId):
        drivers.terminate(sid)


class DownloadingProcessHandler(drivers.BaseDownloadingProgressHandler):
    def __init__(self, js_api: JSApi, sid: SourceId):
        self.js_api = js_api
        self.sid = sid
        super().__init__()

    def init_status(self, status, total_count=None):
        super().init_status(status, total_count)
        total_count = (
            convert_from_bytes(total_count) if total_count else total_count
        )
        self.js_api.evaluate_js(
            f"initStatus({self.sid}, '{status.value}', '{total_count}')"
        )
        if status is drivers.DownloadProcessStatus.FINISHED:
            logger.opt(colors=True).info(
                f"downloading finished: <y>{self.sid}</y>"
            )
        elif status is drivers.DownloadProcessStatus.TERMINATED:
            logger.opt(colors=True).info(
                f"downloading terminated: <y>{self.sid}</y>"
            )

    def show_progress(self) -> None:
        done_count = (
            convert_from_bytes(self.done_count)
            if self.done_count
            else self.done_count
        )
        with suppress(Exception):
            self.js_api.evaluate_js(
                f"downloadingCallback({self.sid}, "
                f"'{done_count}', {self.done_count}, {self.total_count})"
            )

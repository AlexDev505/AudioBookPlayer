from __future__ import annotations

import asyncio
import os
import typing as ty
from contextlib import suppress
from pathlib import Path

import requests
from loguru import logger

import drivers
import local_storage
from database import Database
from models.book import AudioBook, BookSource, BookStatus, SourceId, TextBook
from tools import convert_from_bytes, pretty_view

from .exceptions import BookNotDownloaded, ConnectionFailedError, NotFound
from .js_api import JSApi


class LibraryApi(JSApi):
    def __init__(self):
        super().__init__()

        self._library_search_query: str | None = None
        self._matched_books_bids: list[int] | None = None
        self._removed_books: dict[int, list[SourceId]] = {}
        """ {bid: [sid, ...], ...} """
        self._removed_sources_files: dict[SourceId, tuple[Path, list[str]]] = {}
        """ {sid: (dir_path, [relative_file_path, ...]), ...} """

    def book_by_bid(self, bid: int, listening_data: bool = True):
        if book := Database().get_book_by_bid(bid, with_sources=listening_data):
            logger.opt(colors=True).debug(f"book found: {book:colored}")
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
    def mark_as_new(self, sid: SourceId):
        self._set_status(sid, BookStatus.NEW)

    @SourceId.convert_param
    def mark_as_in_progress(self, sid: SourceId):
        self._set_status(sid, BookStatus.IN_PROGRESS)

    @SourceId.convert_param
    def mark_as_completed(self, sid: SourceId):
        self._set_status(sid, BookStatus.COMPLETED)

    def _set_status(self, sid: SourceId, status: BookStatus):
        if not (dir_path := Database().get_dir_path(sid)):
            raise NotFound(sid=sid)
        Database().set_status(sid, status)
        local_storage.set_status(dir_path, status)

    @SourceId.convert_param
    def set_listening_progress(
        self, sid: SourceId[AudioBook], chapter_index: int, progress: int
    ):
        if not (dir_path := Database().get_dir_path(sid)):
            raise NotFound(sid=sid)
        lp = Database().set_listening_progress(
            sid, int(chapter_index), int(progress)
        )
        local_storage.set_listening_progress(dir_path, lp)

    @SourceId.convert_param
    def set_reading_progress(
        self, sid: SourceId[TextBook], cfi: str, percent: int
    ):
        if not (dir_path := Database().get_dir_path(sid)):
            raise NotFound(sid=sid)
        Database().set_reading_progress(sid, cfi, percent)
        local_storage.set_reading_progress(dir_path, cfi, percent)

    @SourceId.convert_param
    def download_audio_book(self, sid: SourceId[AudioBook], title: str):
        if not (source := Database().get_source_by_sid(sid)):
            raise NotFound(sid=sid)

        try:
            resp = requests.head(source.chapters[0].url)
            if resp.status_code == 410:
                self.fix_chapters(sid, source.url)
        except requests.exceptions.ConnectionError:
            raise ConnectionFailedError()

        drivers.download(sid, DownloadingProcessHandler(self, sid, title))

    @SourceId.convert_param
    def download_text_book(self, sid: SourceId[TextBook], title: str):
        drivers.download(sid, DownloadingProcessHandler(self, sid, title))

    @SourceId.convert_param
    def terminate_download(self, sid: SourceId):
        drivers.terminate(sid)

    def get_downloads(self) -> list[tuple[str, str]]:
        return [
            (str(dph.sid), dph.title)
            for dph in ty.cast(
                list[DownloadingProcessHandler], drivers.get_downloads()
            )
        ]

    @SourceId.convert_param
    def delete_source_files(self, sid: SourceId):
        db = Database()
        if not (source := db.get_source_by_sid(sid)):
            raise NotFound(sid=sid)

        if not source.is_downloaded:
            raise BookNotDownloaded(sid=sid)
        if not (book := db.get_book_by_bid(source.related_book)):
            raise NotFound(bid=source.related_book)

        local_storage.delete(
            book.dir_path / source.dir_path, list(source.files)
        )
        db.clear_source_files(sid)
        logger.opt(colors=True).info(f"source files are deleted: <y>{sid}</y>")

    def remove_book(self, bid: int):
        db = Database()
        if not (book := db.get_book_by_bid(bid, with_sources=True)):
            raise NotFound(bid=bid)

        if sources := {
            SourceId.from_source(source): (source.dir_path, list(source.files))
            for source in book.iter_sources()
            if source.is_downloaded
        }:
            self._removed_books[bid] = list(sources.keys())
            self._removed_sources_files.update(
                {
                    sid: (book.dir_path / source_path, files)
                    for sid, (source_path, files) in sources.items()
                }
            )
            for sid in sources:
                if path := db.get_dir_path(sid):
                    local_storage.mark_as_ignore(path)

        db.remove_book(bid)
        logger.opt(colors=True).info(f"book removed: <y>{book:colored}</y>")
        return dict(
            bid=bid, title=book.title, can_delete=bid in self._removed_books
        )

    def delete_files_of_removed_book(self, bid: int):
        for sid in self._removed_books.pop(bid, []):
            local_storage.delete(*self._removed_sources_files.pop(sid))
            logger.opt(colors=True).info(
                f"source files are deleted: <y>{sid}</y>"
            )

    def open_book_dir(self, bid: int):
        if not (book := Database().get_book_by_bid(bid)):
            raise NotFound(bid=bid)
        if not os.path.exists(book.dir_path):
            raise BookNotDownloaded(bid=bid)
        os.startfile(book.dir_path)

    @staticmethod
    def fix_cover(sid: SourceId[BookSource], source_url: str):
        logger.opt(colors=True).debug(
            f"request: <r>fix cover</r> | <y>{sid}</y>"
        )
        if not (driver := drivers.BaseDriver.get_suitable_driver(source_url)):
            return
        try:
            new_data = asyncio.run(driver().get_book(source_url))
        except requests.exceptions.ConnectionError:
            return
        Database().fix_cover(sid, new_data.source.cover)
        logger.opt(colors=True).info(
            f"new book <y>{sid}</y> cover: {new_data.source.cover}"
        )

    @staticmethod
    def fix_chapters(sid: SourceId[AudioBook], source_url: str):
        logger.opt(colors=True).debug(
            f"request: <r>fix chapters</r> | <y>{sid}</y>"
        )
        if not (driver := drivers.BaseDriver.get_suitable_driver(source_url)):
            raise
        new_data = asyncio.run(driver().get_book(source_url))
        Database().fix_chapters(sid, new_data.source.chapters)
        logger.opt(colors=True).info(f"source <y>{sid}</y> chapters are fixed")


class DownloadingProcessHandler(drivers.BaseDownloadingProgressHandler):
    def __init__(self, js_api: JSApi, sid: SourceId, title: str):
        self.js_api = js_api
        self.sid = sid
        self.title = title
        super().__init__()

    def init_status(self, status, total_count=None):
        super().init_status(status, total_count)
        total_count = (
            convert_from_bytes(total_count)
            if (
                status is drivers.DownloadProcessStatus.DOWNLOADING
                and total_count
            )
            else total_count
        )
        self.js_api.evaluate_js(
            f"initStatus('{self.sid}', '{status.value}', '{total_count}')"
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
            if (
                self.status is drivers.DownloadProcessStatus.DOWNLOADING
                and self.done_count
            )
            else self.done_count
        )
        with suppress(Exception):
            self.js_api.evaluate_js(
                f"downloadingCallback('{self.sid}', "
                f"'{done_count}', {self.done_count}, {self.total_count})"
            )

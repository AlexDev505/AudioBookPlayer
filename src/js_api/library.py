from __future__ import annotations

from loguru import logger

from database import Database
from models.book import BookStatus, SourceType
from tools import pretty_view

from .exceptions import BookNotFound
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
        raise BookNotFound(bid=bid)

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

    def select_audio_source(self, sid: int):
        Database().select_audio_source(sid)

    def mark_audio_book_as_in_progress(self, sid: int):
        Database().mark_as_in_progress(sid, SourceType.AudioBook)

    def mark_audio_book_as_completed(self, sid: int):
        Database().mark_as_completed(sid, SourceType.AudioBook)

    def set_listening_progress(
        self, sid: int, chapter_index: int, progress: int
    ):
        Database().set_listening_progress(
            sid, int(chapter_index), int(progress)
        )

    def select_text_source(self, sid: int):
        Database().select_text_source(sid)

    def set_reading_progress(self, sid: int, cfi: str, percent: int):
        Database().set_reading_progress(sid, cfi, percent)

from __future__ import annotations

import asyncio
import typing as ty
from dataclasses import dataclass
from functools import partial

import aiohttp
import requests
from loguru import logger

from database import Database
from drivers.base_driver import (
    BaseDriver,
    DriverNotAuthenticated,
    LicensedDriver,
)
from models.book import BookStatus
from tools import pretty_view

from .exceptions import (
    BookNotFound,
    ConnectionFailedError,
    NoSuitableDriver,
    NotAuthenticated,
)
from .js_api import JSApi

if ty.TYPE_CHECKING:
    from models.book import BookPreview, RawBook


class LibraryApi(JSApi):
    def __init__(self):
        super().__init__()

        self._library_search_query: str | None = None
        self._matched_books_bids: list[int] | None = None

    def book_by_bid(self, bid: int, listening_data: bool = False):
        if book := Database().get_book_by_bid(bid):
            logger.opt(colors=True).debug(f"book found: {book:styled}")
            return book.asdict()
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

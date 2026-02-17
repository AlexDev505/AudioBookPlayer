from __future__ import annotations

import asyncio
import os
import typing as ty
from dataclasses import asdict, dataclass
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
from models.book import Book
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


@dataclass
class SearchState:
    can_load_more: bool = True
    offset: int = 0


class SearchApi(JSApi):
    SEARCH_LIMIT = 10

    def __init__(self) -> None:
        super().__init__()

        self._query = ""
        self._searching_task: asyncio.Future | None = None
        self._search_states: dict[BaseDriver, SearchState] = {}
        self._search_results: dict[str, BookPreview] = {}
        self._books_found = self._books_updated = self._books_added = 0
        self._found_urls: set[str] = set()

    def get_book_by_url(self, url: str) -> RawBook:
        if not (driver := BaseDriver.get_suitable_driver(url)):
            raise NoSuitableDriver(url)
        try:
            book = driver().get_book(url)
            logger.opt(colors=True).debug(f"book found: {book:colored}")
            return book
        except DriverNotAuthenticated:
            raise NotAuthenticated(driver.driver_name)
        except requests.exceptions.RequestException as e:
            raise ConnectionFailedError(base_exc=e)

    def search_books(
        self, query: str, required_drivers: list[str] | None = None
    ) -> list[dict]:
        if query.startswith("https://"):
            return [self.get_book_by_url(query).to_preview().asdict()]

        if self._searching_task:
            self._searching_task.cancel()
        if self._query != query:
            self._search_results.clear()
            self._search_states.clear()
            self._query = query

        if not self._search_states:
            self._search_states = {
                driver(): SearchState()
                for driver in BaseDriver.drivers
                if (
                    required_drivers is None
                    or driver.driver_name in required_drivers
                )
                and (not issubclass(driver, LicensedDriver) or driver.is_authed)
            }

        return asyncio.run(self._search_books(query))

    async def _search_books(self, query: str) -> list[dict]:
        logger.opt(lazy=True).trace(
            "search params: {data}",
            data=partial(
                pretty_view, dict(query=query, states=self._search_states)
            ),
        )
        self._books_found = self._books_updated = self._books_added = 0
        self._found_urls.clear()
        tasks: list[asyncio.Task[list[BookPreview]]] = []

        for driver, state in self._search_states.items():
            if not state.can_load_more:
                continue
            tasks.append(
                task := asyncio.create_task(
                    driver.search_books(query, self.SEARCH_LIMIT, state.offset)
                )
            )
            task.add_done_callback(
                partial(self._driver_search_callback, driver=driver)
            )

        self._searching_task = asyncio.gather(*tasks, return_exceptions=True)
        try:
            results = await self._searching_task
        except asyncio.CancelledError:
            logger.debug("search cancelled")
            return []
        if all(isinstance(result, ConnectionFailedError) for result in results):
            raise ty.cast(ConnectionFailedError, results[0])

        logger.opt(colors=True).debug(f"<y>{self._books_found}</y> books found")
        logger.opt(colors=True, lazy=True).trace(
            "found urls: {urls}",
            urls=lambda: ", ".join(self._found_urls),
        )
        result = list(self._search_results.values())
        logger.opt(colors=True).debug(
            f"<y>{len(result)}</y> books compiled "
            f"({self._books_added} added, {self._books_updated} updated)"
        )
        return [book.asdict() for book in result]

    def _driver_search_callback(
        self, task: asyncio.Task[list[BookPreview]], driver: BaseDriver
    ) -> None:
        if e := task.exception():
            if isinstance(e, aiohttp.ClientError):
                raise ConnectionFailedError(base_exc=e)
            logger.opt().error(
                f"searching book by {driver.driver_name} driver "
                f"raises {type(e).__name__}: {e}"
            )
            logger.exception(e)
        books = task.result()
        self._search_states[driver].offset += len(books)
        if len(books) < self.SEARCH_LIMIT:
            self._search_states[driver].can_load_more = False
        self._extend_search_results(books)

    def _extend_search_results(self, books: list[BookPreview]) -> None:
        for book in books:
            self._books_found += len(book.urls)
            self._found_urls.update(book.urls)
            if group := self._search_results.get(book.hash):
                group.extend(book)
                self._books_updated += 1
            else:
                self._search_results[book.hash] = book
                self._books_added += 1

    def check_is_sources_exists(self, books: dict[str, list[str]]) -> list[str]:
        """
        :param books: {hash: [source_url, ...]}
        :returns: list of hashes of books that
         all sources already added to library.
        """
        exists_book_hashes = Database().check_is_sources_exists(books)
        logger.opt(colors=True).debug(
            f"<y>{len(exists_book_hashes)}/{len(books)}</y> books exists"
        )
        return exists_book_hashes

    def add_to_library(self, hash: str):
        if not (book_preview := self._search_results.get(hash)):
            raise BookNotFound()

        book_created = False
        db = Database()
        if not (book := db.get_book_by_hash(hash)):
            book = Book.from_book_preview(book_preview)
            db.save(book)
            logger.opt(colors=True).debug(
                f"book added to library: {book:colored}"
            )
            logger.opt(lazy=True).trace(
                "book: {data}",
                data=partial(
                    pretty_view,
                    book.asdict(),
                    multiline=not os.getenv("NO_MULTILINE", False),
                ),
            )
            book_created = True

        sources_added = asyncio.run(
            self._add_to_library(
                db.check_not_exists_sources(book_preview.urls),
                related_bid=book.id,
            )
        )

        return dict(book_created=book_created, sources_added=sources_added)

    async def _add_to_library(self, urls: set[str], related_bid: int) -> int:
        tasks = []
        for source_url in urls:
            if not (driver := BaseDriver.get_suitable_driver(source_url)):
                raise NoSuitableDriver(source_url)
            tasks.append(
                task := asyncio.create_task(driver().get_book(source_url))
            )
            task.add_done_callback(
                partial(self._add_source_to_library, related_bid=related_bid)
            )

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return len(
            list(filter(lambda x: not isinstance(x, Exception), results))
        )

    @staticmethod
    def _add_source_to_library(
        task: asyncio.Task[RawBook], related_bid: int
    ) -> None:
        if book := task.result():
            source = book.source
            source.related_book = related_bid
            Database().save(source)
            logger.opt(colors=True).debug(
                f"source added to library: {source:colored}"
            )
            logger.opt(lazy=True).trace(
                "source: {data}",
                data=partial(
                    pretty_view,
                    source.asdict(),
                    multiline=not os.getenv("NO_MULTILINE", False),
                ),
            )

    def add(self, url: str):
        driver = BaseDriver.get_suitable_driver(url)()
        book = asyncio.run(driver.get_book(url))
        print(asdict(book))

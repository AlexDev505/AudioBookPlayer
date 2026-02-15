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
from tools import pretty_view

from .exceptions import (
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

    def check_is_books_exists(self, hashes: list[str]) -> list[str]:
        exists_book_hashes = Database().check_is_books_exists(hashes)
        logger.opt(colors=True).debug(
            f"<y>{len(exists_book_hashes)}/{len(hashes)}</y> books exists"
        )
        return exists_book_hashes

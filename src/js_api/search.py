from __future__ import annotations

import asyncio
import typing as ty
from dataclasses import dataclass
from functools import partial

import aiohttp
import requests
from loguru import logger

from drivers.base_driver import BaseDriver, DriverNotAuthenticated
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

        self._search_states: dict[BaseDriver, SearchState] = {}
        self._search_results: dict[BookPreview, BookPreview] = {}
        self._books_found: int = 0
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
    ) -> list[BookPreview]:
        if query.startswith("https://"):
            return [self.get_book_by_url(query).to_preview()]

        if not self._search_states:
            self._search_states = {
                driver(): SearchState()
                for driver in BaseDriver.drivers
                if (
                    required_drivers is None
                    or driver.driver_name in required_drivers
                )
            }

        return asyncio.run(self._search_books(query))

    async def _search_books(self, query: str) -> list[BookPreview]:
        logger.opt(lazy=True).trace(
            "search params: {data}",
            data=partial(
                pretty_view, dict(query=query, states=self.search_state)
            ),
        )
        self._books_found = 0
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

        results = await asyncio.gather(*tasks, return_exceptions=True)
        if all(isinstance(result, ConnectionFailedError) for result in results):
            raise ty.cast(ConnectionFailedError, results[0])

        logger.opt(colors=True).debug(f"<y>{self._books_found}</y> books found")
        logger.opt(colors=True, lazy=True).trace(
            "found urls: {urls}",
            urls=lambda: ", ".join(self._found_urls),
        )
        result = list(self._search_results.keys())
        logger.opt(colors=True).debug(f"<y>{len(result)}</y> books compiled")
        return result

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
        self._extend_search_results(task.result())

    def _extend_search_results(self, books: list[BookPreview]) -> None:
        for book in books:
            self._books_found += len(book.urls)
            self._found_urls.update(book.urls)
            if group := self._search_results.get(book):
                group.extend(book)
            else:
                self._search_results[book] = book

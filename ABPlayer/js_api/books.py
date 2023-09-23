from __future__ import annotations

import typing as ty

from drivers import Driver
from .js_api import JSApi


if ty.TYPE_CHECKING:
    pass


class BooksApi(JSApi):
    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[dict]:
        result: list[dict] = []
        limit_per_one_driver = limit // len(Driver.drivers)
        offset_per_one_driver = offset // len(Driver.drivers)
        for driver in Driver.drivers:
            driver = driver()
            try:
                books = driver.search_books(
                    query, limit_per_one_driver, offset_per_one_driver
                )
            except AttributeError:
                continue
            result.extend(
                dict(
                    author=book.author,
                    name=book.name,
                    series_name=book.series_name,
                    reader=book.reader,
                    duration=book.duration,
                    url=book.url,
                    preview=book.preview,
                    driver=book.driver,
                )
                for book in books
            )
        return result

from __future__ import annotations

import typing as ty
from datetime import datetime

import requests.exceptions

from drivers import Driver
from .js_api import JSApi, JSApiError
from database import Database


if ty.TYPE_CHECKING:
    pass


class BooksApi(JSApi):
    def search_books(self, query: str, limit: int = 10, offset: int = 0):
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
        return self.make_answer(result)

    def add_book_to_library(self, url: str):
        if not (driver := Driver.get_suitable_driver(url)):
            return self.error(NoSuitableDriver(book_url=url))
        try:
            book = driver().get_book(url)
        except requests.exceptions.ConnectionError as err:
            return self.error(ConnectionError(err=f"{type(err).__name__}: {err}"))
        with Database(autocommit=True) as db:
            if db.check_is_books_exists([url]):
                return self.error(BookAlreadyAdded())
            book.adding_date = datetime.now()
            db.add_book(book)
        return self.make_answer()

    def check_is_books_exists(self, urls: list[str]):
        with Database() as db:
            return self.make_answer(db.check_is_books_exists(urls))


class ConnectionError(JSApiError):
    code = 1
    message = "Ошибка соединения"


class NoSuitableDriver(JSApiError):
    code = 2
    message = "Нет подходящего драйвера"


class BookAlreadyAdded(JSApiError):
    code = 3
    message = "Книга уже добавлена в библиотеку"

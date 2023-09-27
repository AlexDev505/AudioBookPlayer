from __future__ import annotations

import typing as ty
from datetime import datetime

import requests.exceptions

from database import Database
from drivers import Driver
from models.book import DATETIME_FORMAT
from .js_api import JSApi, JSApiError


if ty.TYPE_CHECKING:
    pass


class BooksApi(JSApi):
    def get_library(
        self,
        limit: int,
        offset: int = 0,
        sort: str | None = None,
        author: str | None = None,
        series: str | None = None,
        favorite: bool | None = None,
        status: str | None = None,
    ):
        with Database() as db:
            books = db.get_libray(limit, offset, sort, author, series, favorite, status)
        return self.make_answer(
            [
                dict(
                    author=book.author,
                    name=book.name,
                    series_name=book.series_name,
                    number_in_series=book.number_in_series,
                    description=book.description,
                    reader=book.reader,
                    duration=book.duration,
                    preview=book.preview,
                    driver=book.driver,
                    status=book.status.value,
                    listening_progress=book.listening_progress,
                    favorite=book.favorite,
                    adding_date=book.adding_date.strftime(DATETIME_FORMAT),
                    downloaded=bool(book.files),
                )
                for book in books
            ]
        )

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

from __future__ import annotations

import os
import sqlite3
import typing as ty
from loguru import logger

from models.book import Book
from .field_types import get_signature, convert_value, adapt_value


DATABASE_PATH = os.environ.get("DATABASE_PATH")
BOOK_SIGNATURE = get_signature(Book)


class Database:
    database_path = DATABASE_PATH

    def __init__(self, autocommit: bool = False):
        self.autocommit = autocommit
        self.conn: sqlite3.Connection | None = None
        self._cursor: sqlite3.Cursor | None = None

    def _connect(self) -> None:
        self.conn = sqlite3.connect(self.database_path)
        self._cursor = self.conn.cursor()

    def __enter__(self) -> ty.Self:
        self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.autocommit:
            self.conn.commit()
        self._cursor.close()
        self.conn.close()

    def _fetchall(self, query: str, *args) -> list[tuple]:
        self._execute(query, *args)
        return self._cursor.fetchall()

    @logger.catch
    def _execute(self, query: str, *args) -> None:
        self._cursor.execute(query, args)

    def create_library(self) -> None:
        fields = [
            f"{field.field_name} {field.sql_type}"
            for field in BOOK_SIGNATURE.values()
            if field.field_name != "id"
        ]
        self._execute(
            "CREATE TABLE IF NOT EXISTS books "
            "(id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL, %s)" % (", ".join(fields))
        )

    def get_libray(self) -> list[Book]:
        return [_convert_book(data) for data in self._fetchall("SELECT * FROM books")]

    def get_book_by_bid(self, bid: int) -> Book | None:
        if books := self._fetchall("SELECT * FROM books WHERE id=?", bid):
            return _convert_book(books[0])

    def check_is_books_exists(self, urls: list[str]) -> list[str]:
        return [
            url[0]
            for url in self._fetchall(
                f"SELECT url FROM books WHERE url IN ({','.join('?'*len(urls))})", *urls
            )
        ]

    def add_book(self, book: Book) -> None:
        fields = {
            field_name: adapt_value(getattr(book, field_name))
            for field_name in BOOK_SIGNATURE.keys()
            if field_name != "id"
        }
        self._execute(
            "INSERT INTO books (%s) VALUES (%s)"
            % (
                ", ".join(fields.keys()),
                ", ".join(["?"] * len(fields)),
            ),
            *fields.values(),
        )

    def save(self, book: Book) -> None:
        if book.id is None:
            raise ValueError()

        fields = {
            field_name: getattr(book, field_name)
            for field_name in BOOK_SIGNATURE.keys()
            if field_name != "id"
        }
        self.update(book.id, **fields)

    def update(self, bid: int, **fields) -> None:
        fields = {field_name: adapt_value(obj) for field_name, obj in fields.items()}
        self._execute(
            "UPDATE books SET %s WHERE id=?"
            % (", ".join(map(lambda x: f"{x}=?", fields.keys()))),
            *fields.values(),
            bid,
        )


def _convert_book(data: tuple[ty.Any]) -> Book:
    if len(data) != len(BOOK_SIGNATURE):
        raise ValueError()

    kwargs = {}
    for field, value in zip(BOOK_SIGNATURE.values(), data):
        kwargs[field.field_name] = convert_value(field, value)

    return Book(**kwargs)

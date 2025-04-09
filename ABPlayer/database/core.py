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
        self.conn = sqlite3.connect(
            self.database_path, detect_types=sqlite3.PARSE_DECLTYPES
        )
        self._cursor = self.conn.cursor()

    def __enter__(self) -> ty.Self:
        self._connect()
        return self

    def _fetchone(self, query: str, *args) -> tuple | None:
        self._execute(query, *args)
        return self._cursor.fetchone()

    def _fetchall(self, query: str, *args) -> list[tuple]:
        self._execute(query, *args)
        return self._cursor.fetchall()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.autocommit:
            self.conn.commit()
        self._cursor.close()
        self.conn.close()

    @logger.catch
    def _execute(self, query: str, *args) -> None:
        self._cursor.execute(query, args)

    def commit(self) -> None:
        self.conn.commit()

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

    def validate_columns(self) -> None:
        exists_fields = [
            field[1] for field in self._fetchall("PRAGMA table_info(books)")
        ]
        columns_to_delete = []
        columns_to_add = []
        for field in BOOK_SIGNATURE.values():
            if field.field_name not in exists_fields:
                columns_to_add.append(field.field_name)
        for field in exists_fields:
            if field not in BOOK_SIGNATURE:
                columns_to_delete.append(field.field_name)
        for field in columns_to_delete:
            self._execute(f"ALTER TABLE books DROP COLUMN {field}")
        for field in columns_to_add:
            self._execute(
                f"ALTER TABLE books ADD COLUMN {field} {BOOK_SIGNATURE[field].sql_type}"
            )
        if columns_to_add:
            book = Book()
            self._execute(
                "UPDATE books SET "
                + ", ".join(f"{field}=?" for field in columns_to_add),
                *(getattr(book, field) for field in columns_to_add),
            )
        if columns_to_delete or columns_to_add:
            logger.debug(
                f"Columns {columns_to_delete} deleted; Columns {columns_to_add} added"
            )
            self.commit()

    def get_libray(
        self,
        limit: int | None = None,
        offset: int = 0,
        sort: str | None = None,
        reverse: bool | None = None,
        author: str | None = None,
        series: str | None = None,
        favorite: bool | None = None,
        status: str | None = None,
        bids: list[int] | None = None,
    ) -> list[Book]:
        q = "SELECT * FROM books"
        args = []

        conditions = []
        if author is not None:
            conditions.append("author=?")
            args.append(author)
        if series is not None:
            conditions.append("series_name=?")
            args.append(series)
        if favorite is not None:
            conditions.append("favorite=?")
            args.append(favorite)
        if status is not None:
            conditions.append("status=?")
            args.append(status)
        if bids is not None:
            conditions.append(f"id IN ({','.join(['?'] * len(bids))})")
            args.extend(bids)
        if conditions:
            q += " WHERE " + " AND ".join(conditions)

        if sort is not None:
            q += f" ORDER BY {sort}"
        if reverse:
            q += " DESC"
        if limit:
            q += " LIMIT ?"
            args.append(limit)
        if offset:
            q += " OFFSET ?"
            args.append(offset)

        return [_convert_book(data) for data in self._fetchall(q, *args)]

    def get_book_by_bid(self, bid: int) -> Book | None:
        if books := self._fetchall("SELECT * FROM books WHERE id=?", bid):
            return _convert_book(books[0])

    def get_books_by_bid(self, *bids: int) -> list[Book] | None:
        if books := self._fetchall(
            f"SELECT {", ".join(BOOK_SIGNATURE.keys())} FROM books "
            f"WHERE id IN [{','.join(['?'] * len(bids))}]",
            *bids,
        ):
            return [_convert_book(book) for book in books]

    def get_book_by_url(self, url: str) -> Book | None:
        if books := self._fetchall("SELECT * FROM books WHERE url=?", url):
            return _convert_book(books[0])

    def get_books_keywords(self) -> dict[int, list[ty.Any]]:
        result = {}
        for book in self._fetchall("SELECT id, name, author, series_name FROM books"):
            result[book[0]] = []
            for field in book[1:]:
                if field:
                    result[book[0]].extend(field.lower().split())
        return result

    def get_all_authors(self) -> list[str]:
        return [obj[0] for obj in set(self._fetchall("SELECT author FROM books"))]

    def get_all_series(self) -> list[str]:
        return [obj[0] for obj in set(self._fetchall("SELECT series_name FROM books"))]

    def get_series_durations(self, series_name: str) -> list[str]:
        return [
            obj[0]
            for obj in self._fetchall(
                "SELECT duration FROM books WHERE series_name=?", series_name
            )
        ]

    def check_is_books_exists(self, urls: list[str]) -> list[str]:
        return [
            url[0]
            for url in self._fetchall(
                f"SELECT url FROM books WHERE url IN ({','.join('?'*len(urls))})", *urls
            )
        ]

    def mark_multi_readers(self, book: Book) -> Book | None:
        if books := self._fetchall(
            "SELECT id, multi_readers FROM books WHERE author=? AND name=?",
            book.author,
            book.name,
        ):
            book.multi_readers = True
            bid = next((book[0] for book in books if not book[1]), None)
            if bid is not None:
                self._execute(f"UPDATE books SET multi_readers=? WHERE id=?", True, bid)
                return self.get_book_by_bid(bid)

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

    def remove_book(self, bid: int) -> None:
        self._execute("DELETE FROM books WHERE id=?", bid)

    def clear(self) -> None:
        self._execute("DELETE FROM books")

    def clear_files(self, *bids: int) -> None:
        if bids:
            self._execute(
                "UPDATE books SET files='{}' "
                f"WHERE id IN ({','.join('?' * len(bids))})",
                *bids,
            )
        else:
            self._execute("UPDATE books SET files='{}'")

    def is_library_empty(self) -> bool:
        return not bool(self._fetchone("SELECT id FROM books"))

    @classmethod
    def init(cls) -> None:
        logger.trace("database initialization")
        with cls() as db:
            db.create_library()
            db.validate_columns()


def _convert_book(data: tuple[ty.Any]) -> Book:
    if len(data) != len(BOOK_SIGNATURE):
        raise ValueError()

    kwargs = {}
    for field, value in zip(BOOK_SIGNATURE.values(), data):
        kwargs[field.field_name] = convert_value(field, value)

    return Book(**kwargs)

from __future__ import annotations

import operator
import os
import typing as ty
from functools import reduce

from aiodbcore import SyncDBCore

from models.book import (
    AudioBook,
    Book,
    BookSource,
    BookStatus,
    SourceType,
    TextBook,
)

if ty.TYPE_CHECKING:
    import aiodbcore.operators


class Database(SyncDBCore[Book | TextBook | AudioBook]):
    def create_library(self):
        self.create_tables()

    def get_library(
        self,
        limit: int | None = None,
        offset: int = 0,
        sort: str = "id",
        reverse: bool | None = None,
        author: str | None = None,
        series: str | None = None,
        favorite: bool | None = None,
        status: BookStatus | None = None,
        bids: list[int] | None = None,
    ):
        where: list[aiodbcore.operators.CmpOperator] = []
        if author is not None:
            where.append(Book.author == author)
        if series is not None:
            where.append(Book.series_name == series)
        if favorite is not None:
            where.append(Book.favorite == favorite)
        if status is not None:
            where.append(Book.status == status)
        if bids is not None:
            where.append(Book.id.contained(bids))
        return self.fetchall(
            Book,
            where=reduce(operator.and_, where),
            order_by=(~getattr(Book, sort)) if reverse else getattr(Book, sort),
            limit=limit,
            offset=offset,
        )

    def get_book_by_bid(self, bid: int) -> Book | None:
        return self.fetchone(Book, where=Book.id == bid)

    def get_books_by_bid(self, *bids: int) -> list[Book]:
        return self.fetchall(Book, where=Book.id.contained(bids))

    def get_book_sources(
        self, bid: int
    ) -> dict[SourceType, list[BookSource]]: ...

    def get_source_by_sid[SourceT: BookSource](
        self, sid: int, source_type: type[SourceT]
    ) -> SourceT | None:
        return self.fetchone(source_type, where=source_type.id == sid)


Database.init(
    f"sqlite://{os.environ['DATABASE_PATH']}",
    check_same_thread=False,
)

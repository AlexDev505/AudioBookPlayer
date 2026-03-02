from __future__ import annotations

import operator
import typing as ty
from functools import reduce

from aiodbcore import SyncDBCore
from aiodbcore.operators import ContainedCmpOperator

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
        books = self.fetchall(
            Book,
            where=reduce(operator.and_, where) if where else None,
            order_by=(~getattr(Book, sort)) if reverse else getattr(Book, sort),
            limit=limit,
            offset=offset,
        )
        for book in books:
            sources = self.get_book_sources(book.id)
            book.add_audio_sources(*sources[SourceType.AudioBook])
            book.add_text_sources(*sources[SourceType.TextBook])
        return books

    def get_book_by_bid(self, bid: int) -> Book | None:
        return self.fetchone(Book, where=Book.id == bid)

    def get_books_by_bid(self, *bids: int) -> list[Book]:
        return self.fetchall(Book, where=Book.id.contained(bids))

    def get_book_by_hash(self, hash: str) -> Book | None:
        return self.fetchone(Book, where=Book.hash == hash)

    def get_book_sources(
        self, bid: int
    ) -> dict[SourceType, ty.Sequence[BookSource]]:
        results: dict[SourceType, ty.Sequence[BookSource]] = {}
        for source_type in SourceType:
            sources = self.fetchall(
                source_type.value, where=source_type.value.related_book == bid
            )
            results[source_type] = sources
        return results

    def get_source_by_sid[SourceT: BookSource](
        self, sid: int, source_type: type[SourceT]
    ) -> SourceT | None:
        return self.fetchone(source_type, where=source_type.id == sid)

    def check_is_sources_exists(self, books: dict[str, list[str]]) -> list[str]:
        return [
            hash
            for hash, urls in books.items()
            if (
                len(urls)
                == ty.cast(
                    tuple,
                    self.provider.fetchone(
                        f"""
                        SELECT Count(*) FROM ({
                            " UNION ALL ".join(
                                f"SELECT url FROM {source_type.value.__name__}"
                                for source_type in SourceType
                            )
                        }) WHERE url IN ({", ".join(["?"] * len(urls))})
                        """,
                        urls,
                    ),
                )[0]
            )
        ]

    def check_not_exists_sources(self, urls: set[str]) -> set[str]:
        return urls.difference(
            {
                url[0]
                for url in self.provider.fetchall(
                    f"""
                    SELECT url FROM ({
                        " UNION ALL ".join(
                            f"SELECT url FROM {source_type.value.__name__}"
                            for source_type in SourceType
                        )
                    }) WHERE url IN ({", ".join(["?"] * len(urls))})
                    """,
                    tuple(urls),
                )
            }
        )

from __future__ import annotations

import operator
import typing as ty
from functools import reduce

from aiodbcore import SyncDBCore

from models.book import (
    AudioBook,
    Book,
    BookSource,
    BookStatus,
    ListeningProgress,
    SourceType,
    TextBook,
)

if ty.TYPE_CHECKING:
    import aiodbcore.operators


class Database(SyncDBCore[Book | TextBook | AudioBook]):
    def create_library(self):
        self.create_tables()
        for table in {AudioBook, TextBook}:
            self.provider.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS only_one_selected_{table.__name__}
                        BEFORE UPDATE OF selected
                            ON {table.__name__}
                        WHEN hex(NEW.selected) = hex("true")
                BEGIN
                    UPDATE {table.__name__}
                       SET selected = CAST ('false' AS BLOB)
                     WHERE related_book = OLD.related_book;
                END;
                """
            )
            self.provider.execute(
                f"""
                CREATE TRIGGER IF NOT EXISTS status_sync_{table.__name__}
                         AFTER UPDATE OF status
                            ON {table.__name__}
                BEGIN
                    UPDATE Book
                       SET status = NEW.status
                     WHERE id = NEW.related_book;
                END;
                """
            )

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

    def get_book_by_bid(
        self, bid: int, with_sources: bool = False
    ) -> Book | None:
        book = self.fetchone(Book, where=Book.id == bid)
        if with_sources and book:
            sources = self.get_book_sources(book.id)
            book.add_audio_sources(*sources[SourceType.AudioBook])
            book.add_text_sources(*sources[SourceType.TextBook])
        return book

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

    def select_audio_source(self, sid: int):
        self.update(
            AudioBook, {AudioBook.selected: True}, where=AudioBook.id == sid
        )

    def select_text_source(self, sid: int):
        self.update(
            TextBook, {TextBook.selected: True}, where=TextBook.id == sid
        )

    def _set_status(
        self, sid: int, source_type: SourceType, status: BookStatus
    ):
        self.update(
            source_type.value,
            {source_type.value.status: status},
            where=source_type.value.id == sid,
        )

    def mark_as_in_progress(self, sid: int, source_type: SourceType):
        self._set_status(sid, source_type, BookStatus.IN_PROGRESS)

    def mark_as_completed(self, sid: int, source_type: SourceType):
        self._set_status(sid, source_type, BookStatus.COMPLETED)

    def set_listening_progress(
        self, sid: int, chapter_index: int, progress: int
    ):
        self.update(
            AudioBook,
            {AudioBook.progress: ListeningProgress(chapter_index, progress)},
            where=AudioBook.id == sid,
        )

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
            # Trigger that ensures only one audio/text source is selected per book
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
            # Trigger that syncs book status with audio/text source status
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
            book.add_audio_sources(*self.get_audio_books(book.id))
            book.add_text_sources(*self.get_text_books(book.id))
        return books

    def get_book_by_bid(
        self, bid: int, with_sources: bool = False
    ) -> Book | None:
        book = self.fetchone(Book, where=Book.id == bid)
        if with_sources and book:
            book.add_audio_sources(*self.get_audio_books(book.id))
            book.add_text_sources(*self.get_text_books(book.id))
        return book

    def get_book_by_hash(self, hash: str) -> Book | None:
        return self.fetchone(Book, where=Book.hash == hash)

    def get_audio_books(self, bid: int) -> list[AudioBook]:
        return self.fetchall(AudioBook, where=AudioBook.related_book == bid)

    def get_text_books(self, bid: int) -> list[TextBook]:
        return self.fetchall(TextBook, where=TextBook.related_book == bid)

    def get_source_by_sid[SourceT: BookSource](
        self, sid: int, source_type: type[SourceT]
    ) -> SourceT | None:
        return self.fetchone(source_type, where=source_type.id == sid)

    def check_are_sources_exists(
        self, books: dict[str, list[str]]
    ) -> list[str]:
        """
        :param books: dict like {book_hash: [source_url, ...], ...}
        :returns: list of book hashes that have at least one source
            that does not exist in the database
        """
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
        """
        :returns: set of urls that do not exist in the database
        """
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

    def mark_as_new(self, sid: int, source_type: SourceType):
        self._set_status(sid, source_type, BookStatus.NEW)

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

    def set_reading_progress(self, sid: int, cfi: str, percent: int):
        self.update(
            TextBook,
            {TextBook.progress: cfi, TextBook.progress_percent: percent},
            where=TextBook.id == sid,
        )

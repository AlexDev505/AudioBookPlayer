from __future__ import annotations

import operator
import typing as ty
from functools import lru_cache, partial, reduce

from aiodbcore import SyncDBCore
from loguru import logger

from models.book import (
    AudioBook,
    Book,
    BookSource,
    BookStatus,
    Chapter,
    ListeningProgress,
    SourceId,
    SourceType,
    TextBook,
)
from tools import pretty_view

if ty.TYPE_CHECKING:
    from pathlib import Path

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

    def insert(self, obj):  # type: ignore[override]
        obj = super().insert(obj)
        if isinstance(obj, Book):
            logger.opt(colors=True).debug(
                f"book added to library: {obj:colored}"
            )
            logger.opt(lazy=True).trace(
                "book: {data}", data=partial(pretty_view, obj.asdict())
            )
        elif isinstance(obj, BookSource):
            logger.opt(colors=True).debug(
                f"source added to library: {obj:colored}"
            )
            logger.opt(lazy=True).trace(
                "source: {data}", data=partial(pretty_view, obj.asdict())
            )
        return obj

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
        self, sid: SourceId[SourceT]
    ) -> SourceT | None:
        return self.fetchone(sid.stype, where=sid.stype.id == sid.sid)

    def get_source_by_url(
        self, stype: SourceType, url: str
    ) -> BookSource | None:
        return self.fetchone(stype.value, where=stype.value.url == url)

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

    def select_source(self, sid: SourceId):
        self.update(
            sid.stype, {sid.stype.selected: True}, where=sid.stype.id == sid.sid
        )

    def set_status(self, sid: SourceId, status: BookStatus):
        self.update(
            sid.stype, {sid.stype.status: status}, where=sid.stype.id == sid.sid
        )

    def set_listening_progress(
        self, sid: SourceId[AudioBook], chapter_index: int, progress: int
    ) -> ListeningProgress:
        self.update(
            AudioBook,
            {
                AudioBook.progress: (
                    lp := ListeningProgress(chapter_index, progress)
                )
            },
            where=AudioBook.id == sid.sid,
        )
        return lp

    @lru_cache
    def get_dir_path(self, sid: SourceId) -> Path | None:
        if not (
            source := self.fetchone(sid.stype, where=sid.stype.id == sid.sid)
        ):
            return None
        if not (
            book := self.fetchone(Book, where=Book.id == source.related_book)
        ):
            return None
        return book.dir_path / source.dir_path

    def set_reading_progress(
        self, sid: SourceId[TextBook], cfi: str, percent: int
    ):
        self.update(
            TextBook,
            {TextBook.progress: cfi, TextBook.progress_percent: percent},
            where=TextBook.id == sid.sid,
        )

    def remove_book(self, bid: int):
        self.delete(TextBook, where=TextBook.related_book == bid)
        self.delete(AudioBook, where=AudioBook.related_book == bid)
        self.delete(Book, where=Book.id == bid)

    def remove_source(self, sid: SourceId):
        self.delete(sid.stype, where=sid.stype.id == sid.sid)

    def clear_source_files(self, sid: SourceId):
        self.update(
            sid.stype, {sid.stype.files: []}, where=sid.stype.id == sid.sid
        )

    def clear_sources_files(self, sids: list[SourceId[BookSource]]):
        sources: dict[ty.Type[BookSource], list[int]] = {}
        for sid in sids:
            sources.setdefault(sid.stype, []).append(sid.sid)
        for stype, stype_sids in sources.items():
            self.update(
                stype,  # type: ignore
                {stype.files: []},
                where=stype.id.contained(stype_sids),
            )

    def clear_all_files(self):
        for stype in SourceType:
            self.update(stype.value, {stype.value.files: []})

    def remove_self_loaded_sources(self):
        self.delete(AudioBook, where=AudioBook.url.like("file://%"))
        self.delete(TextBook, where=TextBook.url.like("file://%"))

    def is_library_empty(self) -> bool:
        return self.fetchone(Book) is None

    def fix_cover(self, sid: SourceId, cover: str):
        self.update(
            sid.stype, {sid.stype.cover: cover}, where=sid.stype.id == sid.sid
        )

    def fix_chapters(self, sid: SourceId[AudioBook], chapters: list[Chapter]):
        self.update(
            AudioBook,
            {AudioBook.chapters: chapters},
            where=AudioBook.id == sid.sid,
        )

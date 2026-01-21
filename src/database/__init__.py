import os

from aiodbcore import SyncDBCore

from models.book import AudioBook, Book, BookSource, TextBook


class Database(SyncDBCore[Book | TextBook | AudioBook]):
    def get_book_by_bid(self, bid: int) -> Book | None:
        return self.fetchone(Book, where=Book.id == bid)

    def get_source_by_sid[SourceT: BookSource](
        self, sid: int, source_type: type[SourceT]
    ) -> SourceT | None:
        return self.fetchone(source_type, where=source_type.id == sid)


Database.init(
    f"sqlite://{os.environ['DATABASE_PATH']}",
    check_same_thread=False,
)

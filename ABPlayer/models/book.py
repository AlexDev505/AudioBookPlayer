from __future__ import annotations

import os
import typing as ty
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from functools import partial
from pathlib import Path

from loguru import logger
from orjson import orjson
from tools import pretty_view

DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


@dataclass
class BookItem:
    """
    Chapter of the book.
    """

    file_url: str  # URL of the file for downloading
    file_index: int  # File number (Numbering starts from one)
    title: str  # Chapter title
    start_time: int  # Time (in seconds) when the chapter starts
    end_time: int  # Time (in seconds) when the chapter ends

    @property
    def duration(self) -> int:
        """
        Duration of the chapter (in seconds).
        """
        return self.end_time - self.start_time


class BookItems(list[BookItem]):
    """
    List of chapters.
    Represented as a list of dictionaries.
    """

    def __init__(self, items: list[BookItem | dict[str, str | int]] = ()):
        super().__init__(
            BookItem(**item) if isinstance(item, dict) else item
            for item in items
        )

    def to_dump(self) -> list[dict]:
        return [asdict(item) for item in self]


class Status(Enum):
    """
    Book status.
    """

    NEW = "new"  # New book
    STARTED = "started"  # Started listening
    FINISHED = "finished"  # Finished listening


@dataclass
class StopFlag:
    """
    The mark where the user stopped listening.
    Stored in the database as a dictionary.
    """

    item: int = 0  # Chapter (Index)
    time: int = 0  # Second


class BookFiles(dict):
    """
    Audio files of the book. Dictionary: dict[str, str] {<file name>: <hash>}
    """


@dataclass
class Book:
    """
    Class describing how books are stored in the database,
    as well as what data drivers parse from websites.
    """

    id: int | None = None
    author: str = ""
    name: str = ""
    series_name: str = ""
    number_in_series: str = ""
    description: str = ""  # Description
    reader: str = ""  # Reader
    duration: str = ""  # Duration
    url: str = ""  # Book URL
    preview: str = ""  # Preview (cover) URL
    driver: str = ""  # Driver used for the website
    items: BookItems = field(default_factory=BookItems)  # List of chapters
    status: Status = Status.NEW
    stop_flag: StopFlag = field(default_factory=StopFlag)
    favorite: bool = False
    files: BookFiles = field(default_factory=BookFiles)
    adding_date: datetime = field(default=datetime(2007, 5, 23))
    multi_readers: bool = False

    @property
    def book_path(self) -> str:
        """
        :returns: Relative path to the book in the library.
        """
        path = path = os.path.join("./", self.author)
        if self.series_name:
            book_name = (
                f"{str(self.number_in_series).rjust(2, '0')}. {self.name}"
            )
            path = os.path.join(path, self.series_name, book_name)
        else:
            path = os.path.join(path, self.name)
        if self.multi_readers:
            path = os.path.join(path, self.reader)
        return path

    @property
    def dir_path(self) -> str:
        """
        :returns: Absolute path to the directory where the book is stored.
        """
        return os.path.abspath(
            os.path.join(os.environ["books_folder"], self.book_path)
        )

    @property
    def preview_path(self) -> str:
        """
        :returns: Absolute path to the book cover file.
        """
        return os.path.join(self.dir_path, "cover.jpg")

    @property
    def listening_progress(self) -> str:
        """
        :returns: Listening progress. (In percentage)
        """
        total = sum([item.duration for item in self.items])
        if not total:
            return "0%"
        cur = (
            sum(
                [
                    item.duration
                    for i, item in enumerate(self.items)
                    if i < self.stop_flag.item
                ]
            )
            + self.stop_flag.time
        )
        return f"{int(round(cur / (total / 100)))}%"

    @classmethod
    def scan_dir(cls, dir_path: str) -> ty.Generator[Book, ty.Any, None]:
        """
        Scans the directory for `.abp` files.
        :returns: Generator of book instances loaded from found files.
        """
        logger.opt(colors=True).debug(
            f"scanning <y>{dir_path}</y> for <r>.abp</r>"
        )
        books_found = 0
        for root, _, file_names in os.walk(dir_path):
            if ".abp" in file_names:
                abp_path = os.path.join(root, ".abp")
                if not (book := Book.load_from_storage(abp_path)):
                    # Remove the file if the book cannot be loaded
                    try:
                        os.remove(abp_path)
                    except IOError:
                        pass
                    continue
                books_found += 1
                yield book

        logger.opt(colors=True).debug(f"books found: <y>{books_found}</y>")

    @classmethod
    def load_from_storage(cls, file_path: str) -> Book | None:
        """
        Creates a book instance from a `.abp` file.
        :returns: Book instance or None.
        """
        logger.opt(colors=True).trace(
            f"loading data from <r>.abp</r> <y>{file_path}</y>"
        )
        try:
            with open(file_path, "rb") as file:
                data = dict(**orjson.loads(file.read()))
            data["items"] = BookItems(data["items"])
            data["status"] = Status(data["status"])
            data["stop_flag"] = StopFlag(**data["stop_flag"])
            data["files"] = BookFiles(data["files"])
            data["adding_date"] = datetime.strptime(
                data["adding_date"], DATETIME_FORMAT
            )
        except (ValueError, TypeError) as err:
            logger.opt(colors=True).debug(
                f"error while loading book from <r>.abp</r> <y>{file_path}</y> : "
                f"<lr>{type(err).__name__}: {err}</lr>"
            )
            return

        if "multi_readers" not in data:
            data["multi_readers"] = False

        signature = ty.get_type_hints(cls)
        del signature["id"]
        try:
            if len(signature) != len(data):
                raise ValueError("wrong fields count")
            for fiend_name, field_type in signature.items():
                if (value := data.get(fiend_name)) is None:
                    raise ValueError(f"field `{fiend_name}` not found")
                elif (value_type := type(value)) is not field_type:
                    raise ValueError(
                        f"field value of `{fiend_name}` has `{value_type}` type, "
                        f"but expected `{field_type}`"
                    )
        except ValueError as err:
            logger.opt(colors=True).debug(
                f"incorrect data in <r>.abp</r> <y>{file_path}</y>: {err}"
            )
            return

        book = Book(**data)
        if not str(Path(file_path).parent).endswith(
            book_path := book.book_path[2:]
        ):
            logger.opt(colors=True).debug(
                f"incorrect <r>.abp</r> file path <y>{file_path}</y> "
                f"it's not ends on <y>{book_path}</y>"
            )
            return

        logger.opt(lazy=True).trace(
            "book loaded: {data}",
            data=partial(
                pretty_view,
                book.to_dump(),
                multiline=not os.getenv("NO_MULTILINE", False),
            ),
        )

        return book

    def save_to_storage(self) -> None:
        """
        Saves the book to a `.abp` file.
        """
        logger.opt(colors=True).debug(
            f"{self:styled} saved to <r>.abp</r>: <y>{self.abp_file_path}</y>"
        )
        with open(self.abp_file_path, "wb") as file:
            file.write(orjson.dumps(self.to_dump()))

    def to_dump(self) -> dict:
        return dict(
            author=self.author,
            name=self.name,
            series_name=self.series_name,
            number_in_series=self.number_in_series,
            description=self.description,
            reader=self.reader,
            duration=self.duration,
            url=self.url,
            preview=self.preview,
            driver=self.driver,
            items=self.items.to_dump(),
            status=self.status.value,
            stop_flag=asdict(self.stop_flag),
            favorite=self.favorite,
            files=self.files,
            adding_date=self.adding_date.strftime(DATETIME_FORMAT),
            multi_readers=self.multi_readers,
        )

    @property
    def abp_file_path(self) -> str:
        return os.path.join(self.dir_path, ".abp")

    def __repr__(self):
        return f"Book(id={self.id}, name={self.name}, url={self.url})"

    def __format__(self, format_spec):
        if format_spec == "styled":
            return (
                f"<g>Book</g><w>("
                f"<le>id</le>=<y>{self.id}</y>, "
                f"<le>name</le>=<y>{self.name}</y>, "
                f"<le>url</le>=<y>{self.url}</y>)</w>"
            )
        return repr(self)


__all__ = [
    "BookItem",
    "BookItems",
    "Status",
    "StopFlag",
    "BookFiles",
    "Book",
    "DATETIME_FORMAT",
]

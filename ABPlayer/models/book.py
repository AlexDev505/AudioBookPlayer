from __future__ import annotations

import os
import typing as ty
from dataclasses import dataclass, field, asdict
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
    Глава книги.
    """

    file_url: str  # Ссылка на файл, для скачивания
    file_index: int  # Номер файла(Нумерация с единицы)
    title: str  # Название главы
    start_time: int  # Время (в секундах), когда начинается глава
    end_time: int  # Время (в секундах), когда заканчивается глава

    @property
    def duration(self) -> int:
        return self.end_time - self.start_time


class BookItems(list):
    """
    Список глав.
    В Базе данных храниться как список словарей.
    """

    def __init__(self, items: list[BookItem | dict[str, str | int]] = ()):
        super().__init__(
            BookItem(**item) if isinstance(item, dict) else item for item in items
        )

    def __getitem__(self, item) -> BookItem:
        return super().__getitem__(item)

    def to_dump(self) -> list[dict]:
        return [asdict(item) for item in self]


class Status(Enum):
    """
    Статус книги.
    """

    NEW = "new"  # Новая книга
    STARTED = "started"  # Начал слушать
    FINISHED = "finished"  # Закончил слушать


@dataclass
class StopFlag:
    """
    Отметка, на которой пользователь остановил прослушивание.
    В базе данных храниться как словарь.
    """

    item: int = 0  # Глава(Индекс)
    time: int = 0  # Секунда


class BookFiles(dict):
    """
    Аудио файлы книги. Словарь: dict[str, str] {<имя файла>: <хеш>}
    """


@dataclass
class Book:
    """
    Класс, описывающий, как книги, хранятся в базе данных,
    а так же какие данные драйвера парсят с сайтов.
    """

    id: int | None = None
    author: str = ""
    name: str = ""
    series_name: str = ""
    number_in_series: str = ""
    description: str = ""  # Описание
    reader: str = ""  # Чтец
    duration: str = ""  # Длительность
    url: str = ""  # Ссылка на книгу
    preview: str = ""  # Ссылка на превью(обложку) книги
    driver: str = ""  # Драйвер, с которым работает сайт
    items: BookItems = field(default_factory=BookItems)  # Список глав
    status: Status = Status.NEW
    stop_flag: StopFlag = field(default_factory=StopFlag)
    favorite: bool = False
    files: BookFiles = field(default_factory=BookFiles)
    adding_date: datetime = field(default=datetime(2007, 5, 23))

    @property
    def book_path(self) -> str:
        """
        :return: Относительный путь к книге в библиотеке.
        """
        if self.series_name:
            return os.path.join(
                "./",
                self.author,
                self.series_name,
                f"{str(self.number_in_series).rjust(2, '0')}. {self.name}",
            )
        return os.path.join("./", self.author, self.name)

    @property
    def dir_path(self) -> str:
        """
        :return: Абсолютный путь к директории, в которой храниться книга.
        """
        return os.path.abspath(os.path.join(os.environ["books_folder"], self.book_path))

    @property
    def preview_path(self) -> str:
        """
        :return: Абсолютный путь к файлу обложки книги.
        """
        return os.path.join(self.dir_path, "cover.jpg")

    @property
    def listening_progress(self):
        """
        :return: Прогресс прослушивания. (В процентах)
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
    def scan_dir(cls, dir_path: str) -> list[Book]:
        logger.opt(colors=True).debug(f"scanning <y>{dir_path}</y> for <r>.abp</r>")
        books: list[Book] = []
        for root, _, file_names in os.walk(dir_path):
            if ".abp" in file_names:
                abp_path = os.path.join(root, ".abp")
                if not (book := Book.load_from_storage(abp_path)):
                    try:
                        os.remove(abp_path)
                    except IOError:
                        pass
                    continue
                books.append(book)

        logger.opt(colors=True).debug(f"books found: <y>{len(books)}</y>")

        return books

    @classmethod
    def load_from_storage(cls, file_path: str) -> Book | None:
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
        if not str(Path(file_path).parent).endswith(book_path := book.book_path[2:]):
            logger.opt(colors=True).debug(
                f"incorrect <r>.abp</r> file path <y>{file_path}</y> "
                f"it's not ends on <y>{book_path}</y>"
            )

        logger.opt(lazy=True).trace(
            "book loaded: {data}",
            data=partial(pretty_view, book.to_dump(), multiline=True),
        )

        return book

    def save_to_storage(self) -> None:
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

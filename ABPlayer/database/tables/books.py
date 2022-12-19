from __future__ import annotations

import os
import typing as ty
from ast import literal_eval
from datetime import datetime
from dataclasses import dataclass, field

import msgspec
from sqlite3_api import Table
from sqlite3_api.field_types import Dict, FieldType, List

from database.tools import replace_quotes


@dataclass
class BookItem:
    """
    Глава книги.
    В базе данных храниться как словарь.
    """

    file_url: str  # Ссылка на файл, для скачивания
    file_index: int  # Номер файла(Нумерация с единицы)
    title: str  # Название главы
    start_time: int  # Время (в секундах), когда начинается глава
    end_time: int  # Время (в секундах), когда заканчивается глава

    def __post_init__(self):
        self.title = replace_quotes(self.title)

    def __repr__(self):
        return str(vars(self))

    @property
    def duration(self) -> int:
        return self.end_time - self.start_time


class BookItems(List):
    """
    Список глав.
    В Базе данных храниться как список словарей.
    """

    def __init__(self, items: ty.List[ty.Dict[str, ty.Union[str, int]]] = ()):
        super(BookItems, self).__init__(BookItem(**item) for item in items)


class Status(FieldType):
    """
    Статус книги.
    В базе данных хранится как строка.
    """

    new = "new"  # Новая книга
    started = "started"  # Начал слушать
    finished = "finished"  # Закончил слушать

    @classmethod
    def converter(cls, obj: bytes) -> str:
        return obj.decode("utf-8")


@dataclass
class StopFlag(FieldType):
    """
    Отметка, на которой пользователь остановил прослушивание.
    В базе данных храниться как словарь.
    """

    item: int = 0  # Глава(Индекс)
    time: int = 0  # Секунда

    def __repr__(self):
        return str(vars(self))

    @classmethod
    def converter(cls, obj: bytes) -> StopFlag:
        return cls(**literal_eval(obj.decode("utf-8")))


class Bool(FieldType):
    """
    Булевая переменная.
    В базе данных храниться в виде `0` или `1`.
    При выборке данных из бд, конвертируется в `True` или `False`.
    """

    @staticmethod
    def adapter(obj: bool) -> bytes:
        return str(int(obj)).encode()

    @classmethod
    def converter(cls, obj: bytes) -> bool:
        return bool(int(obj.decode("utf-8")))


class DateTime(FieldType, datetime):
    format = '%Y-%m-%d %H:%M:%S'
    @staticmethod
    def adapter(obj: DateTime) -> bytes:
        return obj.strftime(obj.format).encode()
    @classmethod
    def converter(cls, obj: bytes) -> DateTime:
        return cls.strptime(obj.decode("utf-8"), cls.format)


class BookFiles(Dict):
    """
    Аудио файлы книги. Словарь: ty.Dict[str, str] {<имя файла>: <хеш>}
    """


@dataclass
class Book:
    """
    Класс, описывающий, как книги, хранятся в базе данных,
    а так же какие данные драйвера парсят с сайтов.
    """

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

    def __post_init__(self):
        self.author = replace_quotes(self.author)
        self.name = replace_quotes(self.name)

    @property
    def book_path(self) -> str:
        """
        :return: Путь относительный путь к книге в библиотеке.
        """
        if self.series_name:
            return os.path.join(
                "./",
                self.author,
                self.series_name,
                f"{self.number_in_series.rjust(2, '0')}. {self.name}",
            )
        return os.path.join("./", self.author, self.name)

    @property
    def dir_path(self) -> str:
        """
        :return: Абсолютный путь к директории, в которой храниться книга.
        """
        return os.path.abspath(os.path.join(os.environ["books_folder"], self.book_path))

    def __repr__(self):
        return f"Book(name={self.name}, author={self.author}, url={self.url})"


class Books(Table, Book):
    """
    Класс, описывающий, как книги, хранятся в базе данных.
    """

    status: Status = Status.new
    stop_flag: StopFlag = StopFlag()
    favorite: Bool = False
    files: BookFiles = BookFiles()
    adding_date: DateTime = DateTime(2007, 5, 23)
    file_path: str = ""

    @property
    def listening_progress(self):
        """
        :return: Прогресс прослушивания. (В процентах)
        """
        total = sum([item.end_time - item.start_time for item in self.items])
        if not total:
            return "0%"
        cur = (
            sum(
                [
                    item.end_time - item.start_time
                    for i, item in enumerate(self.items)
                    if i < self.stop_flag.item
                ]
            )
            + self.stop_flag.time
        )
        return f"{int(round(cur / (total / 100)))}%"

    @classmethod
    def load_from_storage(cls, file_path: str) -> dict:
        with open(file_path, "rb") as file:
            data = dict(**msgspec.json.decode(file.read()), file_path=file_path)
        data["items"] = BookItems(data["items"])
        data["stop_flag"] = StopFlag(**data["stop_flag"])
        data["files"] = BookFiles(data["files"])
        data["adding_date"] = DateTime.strptime(data["adding_date"], DateTime.format)
        return data

    def save_to_storage(self) -> None:
        with open(self.file_path, "wb") as file:
            file.write(
                msgspec.json.encode(
                    dict(
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
                        items=self.items,
                        status=self.status,
                        stop_flag=self.stop_flag,
                        favorite=self.favorite,
                        files=self.files,
                        adding_date=self.adding_date.strftime(DateTime.format)
                    )
                )
            )

    def __repr__(self):
        if self.id is not None:
            return f"Books(id={self.id}, name={self.name}, url={self.url})"
        else:
            return f"Books table connection"

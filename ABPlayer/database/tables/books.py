from __future__ import annotations

import os
import typing as ty
from ast import literal_eval
from dataclasses import dataclass, field

from sqlite3_api import Table
from sqlite3_api.field_types import List, FieldType

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


@dataclass
class Book:
    """
    Класс, описывающий, как книги, хранятся в базе данных,
    а так же какие данные драйвера парсят с сайтов.
    """

    author: str = ""
    name: str = ""
    description: str = ""  # Описание
    reader: str = ""  # Чтец
    duration: str = ""  # Длительность
    url: str = ""  # Ссылка на книгу
    preview: str = ""  # Ссылка на превью(обложку) книги
    driver: str = ""  # Драйвер, с которым работает сайт
    items: BookItems[BookItem] = field(default_factory=BookItems)  # Список глав

    def __post_init__(self):
        self.author = replace_quotes(self.author)
        self.name = replace_quotes(self.name)

    @property
    def dir_path(self) -> str:
        """
        :return: Путь к директории, в которой храниться книга.
        """
        return os.path.abspath(
            os.path.join(os.environ["dir_with_books"], self.author, self.name)
        )


class Books(Table, Book):
    """
    Класс, описывающий, как книги, хранятся в базе данных.
    """

    status: Status = Status.new
    stop_flag: StopFlag = StopFlag()
    favorite: Bool = False

    @property
    def listening_progress(self):
        """
        :return: Прогресс прослушивания. (В процентах)
        """
        total = sum([item.end_time - item.start_time for item in self.items])
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

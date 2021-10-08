from __future__ import annotations

import typing as ty
from dataclasses import dataclass, field
from ast import literal_eval

from sqlite3_api import Table
from sqlite3_api.field_types import List, FieldType

from database.tools import replace_quotes


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

    def __post_init__(self):
        self.title = replace_quotes(self.title)

    def __repr__(self):
        return str(vars(self))


class BookItems(List):
    """
    Список глав.
    """

    def __init__(self, items: ty.List[ty.Dict[str, ty.Union[str, int]]] = ()):
        super(BookItems, self).__init__(BookItem(**item) for item in items)


class Status(FieldType):
    """
    Статус книги.
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
    """

    item: int = 0  # Глава
    time: int = 0  # Секунда

    def __repr__(self):
        return str(vars(self))

    @classmethod
    def converter(cls, obj: bytes) -> StopFlag:
        return cls(**literal_eval(obj.decode("utf-8")))


@dataclass
class Book:
    """
    Класс, описывающий, как книги, хранятся в базе данных.
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


class Books(Table, Book):
    """
    Класс, для взаимодействия с базой данных.
    """

    status: Status = Status.new
    stop_flag: StopFlag = StopFlag()

from __future__ import annotations

import typing as ty
from dataclasses import dataclass, field

from sqlite3_api import Table
from sqlite3_api.field_types import List

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


@dataclass
class Book:
    """
    Класс, описывающий, как книги, хранятся в базе данных.
    """

    author: str = None
    name: str = None
    url: str = None  # Ссылка на книгу
    preview: str = None  # Ссылка на превью(обложку) книги
    driver: str = None  # Драйвер, с которым работает сайт
    items: BookItems[BookItem] = field(default_factory=BookItems)  # Список глав

    def __post_init__(self):
        self.author = replace_quotes(self.author)
        self.name = replace_quotes(self.name)


class Books(Table, Book):
    """
    Класс, для взаимодействия с базой данных.
    """

from __future__ import annotations

import typing as ty
from dataclasses import dataclass, field

from sqlite3_api import Table
from sqlite3_api.field_types import List


@dataclass
class BookItem:
    """
    Глава книги.
    """

    file_url: str  # Ссылка на файл, для скачивания
    title: str  # Название главы
    start_time: int  # Время (в секундах), когда начинается глава
    end_time: int  # Время (в секундах), когда заканчивается глава

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
    items: BookItems = field(default_factory=BookItems)  # Список глав


class Books(Table, Book):
    """
    Класс, для взаимодействия с базой данных.
    """

import os

from .tables.books import Books, Book, BookItems, BookItem
from .tables.config import Config

# Создаём таблицы
Config(os.environ["DB_PATH"]).create_table()

__all__ = ["Books", "Book", "BookItems", "BookItem", "Config"]

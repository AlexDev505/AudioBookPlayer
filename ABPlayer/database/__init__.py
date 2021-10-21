import os
from .tables.books import Books, Book, BookItems, BookItem
from .tables.config import Config

os.environ["DB_PATH"] = os.path.join(os.environ["APP_DIR"], "database.sqlite")

Books(os.environ["DB_PATH"]).create_table()  # Создаём таблицу
Config(os.environ["DB_PATH"]).create_table()  # Создаём таблицу

import os
from .tables.books import Books, Book, BookItems, BookItem

os.environ["DB_PATH"] = os.path.join(os.environ["APP_DIR"], "database.sqlite")

Books(os.environ["DB_PATH"]).create_table()

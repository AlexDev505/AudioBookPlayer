import os
from sqlite3_api import Table


class Config(Table):
    books_folder: str = "книги"
    theme: str = ""

    def add_to_env(self):
        for field in self.get_fields():
            os.environ[field] = self.__dict__[field]

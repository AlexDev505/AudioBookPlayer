import os
import typing as ty

from sqlite3_api import Table


class Config(Table):
    """
    Класс, описывающий как конфигурация хранится в базе данных.
    """

    books_folder: str = "книги"
    theme: str = ""

    @classmethod
    def init(cls) -> None:
        """
        Инициализация конфигурации.
        Создание записи в бд, если не существует.
        Добавление в виртуальное окружение.
        """
        db = cls(os.environ["DB_PATH"])
        config = db.filter()
        if not config:
            db.insert()
            config = db.filter()

        config.add_to_env()

    def add_to_env(self) -> None:
        """
        Добавление конфигурации в виртуальное окружение.
        """
        for field in self.get_fields():
            os.environ[field] = self.__dict__[field]

    def update(self, **fields: [str, ty.Any]) -> None:
        """
        Дополняет стандартную функцию.
        Обновляет данные как в бд, так и в виртуальном окружении.
        """
        super(Config, self).update(**fields)
        self.add_to_env()

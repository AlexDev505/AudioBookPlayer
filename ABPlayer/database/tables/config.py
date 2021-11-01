import os
import typing as ty

from sqlite3_api import Table


class Config(Table):
    """
    Класс, описывающий как конфигурация хранится в базе данных.
    """

    books_folder: str = os.environ["DEFAULT_BOOKS_FOLDER"]  # Директория с книгами
    theme: str = "Тёмная"

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

    @classmethod
    def update(cls, **fields: [str, ty.Any]) -> None:
        """
        Дополняет стандартную функцию.
        Обновляет данные как в бд, так и в виртуальном окружении.
        """
        config = cls(os.environ["DB_PATH"]).filter()
        super(Config, config).update(**fields)
        config.add_to_env()

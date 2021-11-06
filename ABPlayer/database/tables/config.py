import os
import typing as ty

from sqlite3_api import Table
from loguru import logger


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
        logger.trace("Configuration initialization")
        db = cls(os.environ["DB_PATH"])
        config = db.filter()
        if not config:
            logger.debug("Config table is empty")
            db.insert()
            config = db.filter()
        elif isinstance(config, list):
            logger.warning("There is more than one record in the config table")
            db.api.execute("DROP TABLE config")
            db.insert()
            config = db.filter()

        if not os.path.isdir(config.books_folder):
            logger.debug(f"Directory with books ({config.books_folder}) does not exist")
            if not os.path.exists(os.environ["DEFAULT_BOOKS_FOLDER"]):
                os.mkdir(os.environ["DEFAULT_BOOKS_FOLDER"])
            if config.books_folder != os.environ["DEFAULT_BOOKS_FOLDER"]:
                config.update(books_folder=os.environ["DEFAULT_BOOKS_FOLDER"])
                return

        config.add_to_env()

    def add_to_env(self) -> None:
        """
        Добавление конфигурации в виртуальное окружение.
        """
        logger.trace("Adding configuration to the virtual environment")
        for field in self.get_fields():
            os.environ[field] = self.__dict__[field]

    @classmethod
    def update(cls, **fields: [str, ty.Any]) -> None:
        """
        Дополняет стандартную функцию.
        Обновляет данные как в бд, так и в виртуальном окружении.
        """
        logger.opt(colors=True).debug(
            "Configuration update. "
            + ", ".join((f"<le>{k}</le>=<y>{v}</y>" for k, v in fields.items()))
        )
        config = cls(os.environ["DB_PATH"]).filter()
        super(Config, config).update(**fields)
        config.add_to_env()

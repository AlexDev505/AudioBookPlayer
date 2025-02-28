import os
import typing as ty
from functools import partial
from pathlib import Path

import orjson
from loguru import logger

from tools import pretty_view


FIELDS = {
    "books_folder": os.path.join(os.environ["USERPROFILE"], "documents", "Аудио книги"),
    "dark_theme": "1",
}


def init() -> None:
    logger.trace("configuration initialization")

    if not os.path.exists(os.environ["CONFIG_PATH"]):
        _create_config()
        _add_to_env(FIELDS)
    else:
        config = _load_config()
        config = _validate_config(config)
        logger.opt(lazy=True).trace("config: {data}", data=partial(pretty_view, config))
        _add_to_env(config)


def _create_config() -> None:
    """
    Создает файл конфигурации со значениями по умолчанию.
    """
    with open(os.environ["CONFIG_PATH"], "wb") as file:
        file.write(orjson.dumps(FIELDS))


def _load_config() -> dict:
    """
    Загружает данные из файла конфигурации.
    """
    try:
        with open(os.environ["CONFIG_PATH"], "rb") as file:
            return orjson.loads(file.read())
    except orjson.JSONDecodeError:
        _create_config()
        return FIELDS


def update_config(*, update_env=True, **fields: [str, ty.Any]) -> None:
    """
    Обновляет поля в файле конфигурации.
    :param update_env: True - произойдет обновление переменных окружения.
    :param fields: Поля для обновления.
    """
    logger.opt(colors=True).debug(
        "Configuration update. "
        + ", ".join((f"<le>{k}</le>=<y>{v}</y>" for k, v in fields.items()))
    )
    fields = {field: fields.get(field, os.getenv(field)) for field in FIELDS}
    with open(os.environ["CONFIG_PATH"], "wb") as file:
        file.write(orjson.dumps(fields))
    if update_env:
        _add_to_env(fields)


def _validate_config(config: dict) -> dict:
    """
    Проверяет валидность данных конфигурации.
    Исправляет в случае ошибок.
    :returns: Данные конфигурации.
    """
    if any(key not in FIELDS for key in config):
        config = {field: config.get(field, FIELDS[field]) for field in FIELDS}
        update_config(update_env=False, **config)
    else:
        need_update_config = False

        if config["dark_theme"] not in {"1", "2"}:
            config["dark_theme"] = FIELDS["dark_theme"]
            need_update_config = True
        if not (
            isinstance(config["books_folder"], str)
            and os.path.isdir(config["books_folder"])
        ):
            config["books_folder"] = FIELDS["books_folder"]
            Path(FIELDS["books_folder"]).mkdir(parents=True, exist_ok=True)
            need_update_config = True

        if need_update_config:
            update_config(update_env=False, **config)

    return config


def _add_to_env(config: dict) -> None:
    """
    Добавляет данные конфигурации в переменные окружения.
    """
    logger.trace("adding configuration to the virtual environment")
    for field in FIELDS:
        os.environ[field] = config.get(field)

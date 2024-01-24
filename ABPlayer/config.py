import os
import typing as ty
from functools import partial

import orjson
from loguru import logger

from tools import pretty_view


FIELDS = {
    "books_folder": os.path.join(os.environ["USERPROFILE"], "documents", "Аудио книги"),
    "theme": "тёмная",
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
    with open(os.environ["CONFIG_PATH"], "wb") as file:
        file.write(orjson.dumps(FIELDS))


def _load_config() -> dict:
    try:
        with open(os.environ["CONFIG_PATH"], "rb") as file:
            return orjson.loads(file.read())
    except orjson.JSONDecodeError:
        _create_config()
        return FIELDS


def update_config(*, update_env=True, **fields: [str, ty.Any]) -> None:
    logger.opt(colors=True).debug(
        "Configuration update. "
        + ", ".join((f"<le>{k}</le>=<y>{v}</y>" for k, v in fields.items()))
    )
    with open(os.environ["CONFIG_PATH"], "wb") as file:
        file.write(orjson.dumps(fields))
    if update_env:
        _add_to_env(fields)


def _validate_config(config: dict) -> dict:
    if len(config) != len(FIELDS):
        config = {field: config.get(field) for field in FIELDS}
        update_config(update_env=False, **config)
    return config


def _add_to_env(config: dict) -> None:
    logger.trace("adding configuration to the virtual environment")
    for field in FIELDS:
        os.environ[field] = config.get(field)

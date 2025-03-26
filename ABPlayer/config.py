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
    "language": "ru",
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
    Creates a configuration file with default values.
    """
    with open(os.environ["CONFIG_PATH"], "wb") as file:
        file.write(orjson.dumps(FIELDS))


def _load_config() -> dict:
    """
    Loads data from the configuration file.
    """
    try:
        with open(os.environ["CONFIG_PATH"], "rb") as file:
            return orjson.loads(file.read())
    except orjson.JSONDecodeError:
        _create_config()
        return FIELDS


def update_config(*, update_env=True, **fields: [str, ty.Any]) -> None:
    """
    Updates fields in the configuration file.
    :param update_env: True - environment variables will be updated.
    :param fields: Fields to update.
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
    Validates the configuration data.
    Fixes in case of errors.
    :returns: Configuration data.
    """
    if any(key not in FIELDS for key in config):
        config = {field: config.get(field, FIELDS[field]) for field in FIELDS}
        update_config(update_env=False, **config)
    else:
        need_update_config = False

        if config.get("dark_theme") not in {"0", "1"}:
            config["dark_theme"] = FIELDS["dark_theme"]
            need_update_config = True
        if not (
            isinstance(config.get("books_folder"), str)
            and os.path.isdir(config.get("books_folder"))
        ):
            config["books_folder"] = FIELDS["books_folder"]
            Path(FIELDS["books_folder"]).mkdir(parents=True, exist_ok=True)
            need_update_config = True
        if config.get("language") not in {"ru", "en"}:
            config["language"] = FIELDS["language"]
            need_update_config = True

        if need_update_config:
            update_config(update_env=False, **config)

    return config


def _add_to_env(config: dict) -> None:
    """
    Adds configuration data to environment variables.
    """
    logger.trace("adding configuration to the virtual environment")
    for field in FIELDS:
        os.environ[field] = config.get(field)

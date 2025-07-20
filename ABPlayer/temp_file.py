"""

Implements interaction with a file that stores temporary data.

The data in the file is stored in the following format:
<key>: <data type> = <value>
<key>: <data type> = <value>
<key>: <data type> = <value>
...

Each entry starts on a new line.
The following data types are available for storage: str, int, float, bool.

"""

import os
import re
from functools import partial

from loguru import logger
from tools import pretty_view


def load() -> dict[str, str | int | float | bool]:
    """
    Reads data from the file.
    :returns: Dictionary with data.
    """
    logger.opt(colors=True).trace(
        f"loading data from <y>{os.environ['TEMP_PATH']}</y>"
    )
    # Создаём файл
    if not os.path.isfile(os.environ["TEMP_PATH"]):
        logger.opt(colors=True).debug(
            f"temp file <y>{os.environ['TEMP_PATH']}</y> not found"
        )
        with open(os.environ["TEMP_PATH"], "w", encoding="utf-8"):
            pass

    with open(os.environ["TEMP_PATH"], encoding="utf-8") as file:
        data = file.read().splitlines()
    result = {}
    for item in data:
        match = re.fullmatch(
            r"(?P<key>\w+): (?P<type>str|int|float|bool) = (?P<value>.+)",
            item.strip(),
        )  # Pattern matching
        if match:
            result[match.group("key")] = _adapt_value(
                match.group("value"), match.group("type")
            )
        else:
            logger.debug(
                f"failed to retrieve information from string <y>{item}</y>"
            )

    logger.opt(lazy=True).trace(
        "temp data: {data}", data=partial(pretty_view, result)
    )

    return result


def dump(data: dict[str, str | int | float | bool]) -> None:
    """
    Saves data to a file.
    :param data: Dictionary with data.
    """
    logger.opt(lazy=True).trace(
        "new temp data: {data}", data=partial(pretty_view, data)
    )
    logger.opt(colors=True).trace(
        f"saving a file <y>{os.environ['TEMP_PATH']}</y>"
    )
    result = ""
    for key, value in data.items():
        result += f"{key}: {type(value).__name__} = {_convert_value(value)}\n"

    with open(os.environ["TEMP_PATH"], "w", encoding="utf-8") as file:
        file.write(result.strip())


def update(**fields: str | int | float | bool) -> None:
    """
    Updates/adds values in the file.
    """
    data = load()
    data.update(**fields)
    dump(data)


def delete_items(*keys: str) -> None:
    """
    Deletes entries in the file.
    :param keys: Keys of the entries.
    """
    data = load()
    for name in keys:
        if name in data:
            del data[name]
    dump(data)


def _adapt_value(value: str, value_type: str) -> str | int | float | bool:
    """
    Converts a value obtained from the file to a Python data type.
    :param value: Value from the file.
    :param value_type: Data type.
    :returns: Converted value.
    """
    try:
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        elif value_type == "str":
            return value.replace("\\n", "\n")
        elif value_type == "bool":
            return bool(int(value))
    except ValueError:
        logger.opt(colors=True).debug(
            f"Unable to convert string <y>{value}</y> to type </y>{value_type}</y>"
        )


@logger.catch
def _convert_value(value: str | int | float | bool) -> str:
    """
    Prepares data for saving to a file.
    :param value: Original value.
    :returns: Converted value.
    """
    if isinstance(value, bool):
        return str(int(value))
    elif isinstance(value, (str, int, float)):
        return str(value).replace("\n", "\\n")
    raise ValueError(
        f"Invalid data type {type(value).__name__}, "
        "only str, int, float, bool are expected."
    )

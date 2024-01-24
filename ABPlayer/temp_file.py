"""

Реализует взаимодействие с файлом, хранящим временные данные.

В файле данные хранятся в таком виде:
<ключ>: <тип данных> = <значение>
<ключ>: <тип данных> = <значение>
<ключ>: <тип данных> = <значение>
...

Каждая запись начинается с новой строки.
Для хранения доступны такие типы данных как: str, int, float, bool.

"""

import os
import re
from functools import partial

from loguru import logger

from tools import pretty_view


def load() -> dict[str, str | int | float | bool]:
    """
    Считывает данные из файла.
    :return: Словарь с данными.
    """
    logger.opt(colors=True).trace(f"loading data from <y>{os.environ['TEMP_PATH']}</y>")
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
            r"(?P<key>\w+): (?P<type>str|int|float|bool) = (?P<value>.+)", item.strip()
        )  # Проверка шаблона
        if match:
            result[match.group("key")] = _adapt_value(
                match.group("value"), match.group("type")
            )
        else:
            logger.debug(f"failed to retrieve information from string <y>{item}</y>")

    logger.opt(lazy=True).trace("temp data: {data}", data=partial(pretty_view, result))

    return result


def dump(data: dict[str, str | int | float | bool]) -> None:
    """
    Сохраняет данные в файл.
    :param data: Словарь с данными.
    """
    logger.opt(lazy=True).trace(
        "new temp data: {data}", data=partial(pretty_view, data)
    )
    logger.opt(colors=True).trace(f"saving a file <y>{os.environ['TEMP_PATH']}</y>")
    result = ""
    for key, value in data.items():
        result += f"{key}: {type(value).__name__} = {_convert_value(value)}\n"

    with open(os.environ["TEMP_PATH"], "w", encoding="utf-8") as file:
        file.write(result.strip())


def update(**fields: str | int | float | bool) -> None:
    """
    Обновляет/добавляет значения в файле.
    """
    data = load()
    data.update(**fields)
    dump(data)


def delete_items(*keys: str) -> None:
    """
    Удаляет записи в файле.
    :param keys: Ключи записей.
    """
    data = load()
    for name in keys:
        if name in data:
            del data[name]
    dump(data)


def _adapt_value(value: str, value_type: str) -> str | int | float | bool:
    """
    Преобразует значение полученное из файла в тип данных Python.
    :param value: Значение из файла.
    :param value_type: Тип данных.
    :return:
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
    Подготавливает данные для сохранения в файл.
    :param value: Исходное значение.
    :return: Преобразованное значение.
    """
    if isinstance(value, bool):
        return str(int(value))
    elif isinstance(value, (str, int, float)):
        return str(value).replace("\n", "\\n")
    raise ValueError(
        f"Недопустимый тип данных {type(value).__name__}, "
        "можно хранить только str, int, float, bool"
    )

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

from __future__ import annotations

import os
import re
import typing as ty
import warnings

# Создаём файл
if not os.path.isfile(os.environ["TEMP_PATH"]):
    with open(os.environ["TEMP_PATH"], "w", encoding="utf-8"):
        pass


def load() -> ty.Dict[str, ty.Union[str, int, float, bool]]:
    """
    Считывает данные из файла.
    :return: Словарь с данными.
    """
    with open(os.environ["TEMP_PATH"], encoding="utf-8") as file:
        data = file.read().split("\n")
    result = {}
    for item in data:
        match = re.fullmatch(
            r"(?P<key>\w+): (?P<type>str|int|float) = (?P<value>.+)", item.strip()
        )  # Проверка шаблона
        if match:
            result[match.group("key")] = _adapt_value(
                match.group("value"), match.group("type")
            )
        else:
            warnings.warn(f"Не удалось извлечь информацию из строки '{item}'")
    return result


def dump(data: ty.Dict[str, ty.Union[str, int, float, bool]]) -> None:
    """
    Сохраняет данные в файл.
    :param data: Словарь с данными.
    """
    result = ""
    for key, value in data.items():
        result += f"{key}: {type(value).__name__} = {_convert_value(value)}\n"

    with open(os.environ["TEMP_PATH"], "w", encoding="utf-8") as file:
        file.write(result.strip())


def update(**kwargs: ty.Union[str, int, float]) -> None:
    """
    Обновляет/добавляет значения в файле.
    :param kwargs:
    """
    data = load()
    data.update(**kwargs)
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


def _adapt_value(value: str, value_type: str) -> ty.Union[str, int, float]:
    """
    Преобразует значение полученное из файла в питоновский тип данных.
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
        warnings.warn(f"Невозможно преобразовать строку '{value}' к типу {value_type}")


def _convert_value(value: ty.Union[str, int, float, bool]) -> str:
    """
    Подготавливает питоновский тип данных для сохранения в файл.
    :param value: Исходное значение.
    :return: Преобразованное значение.
    """
    if isinstance(value, (str, int, float)):
        return str(value).replace("\n", "\\n")
    elif isinstance(value, bool):
        return str(int(value))
    raise ValueError(
        f"Недопустимый тип данных {type(value).__name__}, "
        "можно хранить только str, int, float"
    )

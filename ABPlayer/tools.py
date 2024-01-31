from __future__ import annotations

import hashlib
import math
import typing as ty

import pygments.formatters
import pygments.lexers
from loguru import logger


if ty.TYPE_CHECKING:
    from pathlib import Path
    from models.book import Book


def convert_from_bytes(bytes_value: int) -> str:
    """
    :param bytes_value: Число байт.
    :returns: Строка вида <Число> <Единица измерения>
    """
    if bytes_value == 0:
        return "0B"
    size_name = ("б", "КБ", "МБ", "ГБ", "ТБ", "ПБ", "EB", "ZB", "YB")
    i = int(math.floor(math.log(bytes_value, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_value / p, 2)
    return "%s %s" % (s, size_name[i])


def get_file_hash(file_path: ty.Union[str, Path], hash_func=hashlib.sha256) -> str:
    """
    :param file_path: Путь к файлу.
    :param hash_func: Функция хеширования.
    :returns: Хеш файла.
    """
    hash_func = hash_func()  # Инициализируем хеш функцию
    with open(file_path, "rb") as file:
        # Читаем файл по блокам в 64кб,
        # для избежания загрузки больших файлов в оперативную память
        for block in iter(lambda: file.read(65536), b""):
            hash_func.update(block)
    file_hash = hash_func.hexdigest()
    logger.opt(colors=True).trace(
        f"{hash_func.name} of {str(file_path)}: <y>{file_hash}</y>"
    )
    return file_hash


def pretty_view(
    obj: ty.Any, *, multiline: bool = False, indent: int = 4, __finish=True
) -> str:
    """
    Формирует удобно читаемое представление списка/словаря.
    :returns: Строка.
    """
    result = ""

    if isinstance(obj, (dict, list, tuple)):
        if isinstance(obj, dict):
            new_line = (
                "\n"
                if multiline
                and (
                    len(obj) > 4
                    or any(
                        isinstance(x, (dict, list, tuple)) and len(x) > 4
                        for x in obj.values()
                    )
                )
                else ""
            )
            brackets = ("{", "}")
            lines_iter = (
                f'"{key}": {pretty_view(value, multiline=multiline, __finish=False)}'
                for key, value in obj.items()
            )
        else:
            new_line = (
                "\n"
                if multiline
                and (
                    len(obj) > 7 or any(isinstance(x, (dict, list, tuple)) for x in obj)
                )
                else ""
            )
            brackets = ("[", "]")
            lines_iter = (
                pretty_view(item, multiline=multiline, __finish=False) for item in obj
            )

        result += f"{brackets[0]}{new_line}"
        lines = f", {new_line}".join(lines_iter)
        if "\n" in lines:
            lines = " " * indent + lines
            lines = lines.replace("\n", "\n" + " " * indent)
        result += lines
        result += f"{new_line}{brackets[1]}"
    elif obj is None:
        result = f"null"
    elif isinstance(obj, bool):
        result = f"{obj}".lower()
    elif isinstance(obj, (int, float)):
        result = f"{obj}"
    elif isinstance(obj, str):
        obj = obj.replace("\n", "\\n").replace("\r", "\\r").replace('"', '\\"')
        result = f'"{obj}"'

    if __finish:
        result = pygments.highlight(
            result,
            pygments.lexers.JsonLexer(),  # noqa
            pygments.formatters.TerminalFormatter(),  # noqa
        ).strip()
    return result


def make_book_preview(book: Book) -> dict:
    """
    :param book: Экземпляр книги.
    :returns: Словарь с основными полями книги.
    """
    return dict(
        author=book.author,
        name=book.name,
        series_name=book.series_name,
        reader=book.reader,
        duration=book.duration,
        url=book.url,
        preview=book.preview,
        driver=book.driver,
    )

from __future__ import annotations

import hashlib
import math
import typing as ty


if ty.TYPE_CHECKING:
    from pathlib import Path
    from models.book import Book


def convert_from_bytes(bytes_value: int) -> str:
    """
    :param bytes_value: Число байт.
    :return: Строка вида <Число> <Единица измерения>
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
    :return: Хеш файла.
    """
    hash_func = hash_func()  # Инициализируем хеш функцию
    with open(file_path, "rb") as file:
        # Читаем файл по блокам в 64кб,
        # для избежания загрузки больших файлов в оперативную память
        for block in iter(lambda: file.read(65536), b""):
            hash_func.update(block)
    return hash_func.hexdigest()


def make_book_preview(book: Book) -> dict:
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

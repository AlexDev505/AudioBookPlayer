"""

Функции и классы, которые используются в приложении.

"""

from __future__ import annotations

import hashlib
import math
import os
import threading
import typing as ty
from abc import abstractmethod

from PyQt5.QtCore import QObject, QThread
from plyer import notification

if ty.TYPE_CHECKING:
    from pathlib import Path
    from database import Books, Book


class Cache(object):
    """
    Кэш.
    Временно хранит до 4-х объектов.
    """

    def __init__(self):
        self.storage = {}

    def get(self, key: str) -> ty.Any:
        """
        :param key: Ключ к объекту.
        :return: Объект.
        """
        return self.storage.get(key)

    def set(self, key: str, obj: ty.Any) -> None:
        """
        Добавляет объект в кэш.
        :param key: Ключ.
        :param obj: Объект.
        """
        if len(self.storage) >= 4:
            del self.storage[list(self.storage.keys())[0]]
        self.storage[key] = obj


class BaseWorker(QObject):
    """
    Базовый класс для функций, работающих в отдельном потоке.
    """

    def __new__(cls, *args, **kwargs):
        self = super(BaseWorker, cls).__new__(cls)
        self.__init__(*args, **kwargs)
        self.thread = QThread(self)  # Создаем новый поток
        self.moveToThread(self.thread)
        self.thread.started.connect(self._worker)
        return self

    def _worker(self):
        # Изменяем
        threading.currentThread().setName(self.__class__.__name__)
        self.worker()

    @abstractmethod
    def worker(self) -> None:
        """
        Необходимо реализовать в наследуемом классе.
        Функция, которая будет выполняться в другом потоке.
        """

    @abstractmethod
    def connectSignals(self) -> None:
        """
        Необходимо реализовать в наследуемом классе.
        Подключение обработчиков к сигналам.
        """

    def start(self) -> None:
        """
        Запуск потока.
        """
        self.connectSignals()
        self.thread.start()


def convert_into_seconds(seconds: int) -> str:
    """
    :param seconds: Число секунд.
    :return: Строка вида `<часы>:<минуты>:<секунды>`.
    """
    h = seconds // 3600
    m = seconds % 3600 // 60
    s = seconds % 60
    return ((str(h).rjust(2, "0") + ":") if h else "") + ":".join(
        map(lambda x: str(x).rjust(2, "0"), (m, s))
    )


def convert_into_bytes(bytes_value: int) -> str:
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


def pretty_view(data: ty.Union[dict, list], _indent=0) -> str:
    """
    Преобразовывает `data` в более удобный для восприятия вид.
    """

    def adapt_value(obj: ty.Any) -> ty.Any:
        if isinstance(obj, (int, float, bool, dict)) or obj is None:
            return obj
        elif obj.__repr__().startswith("{"):
            return obj.__dict__
        elif obj.__repr__().startswith("["):
            return list(obj)
        else:
            return str(obj)

    def tag(t: str, content: ty.Any) -> str:
        return f"<{t}>{content}</{t}>"

    def dict_(content: dict) -> ty.List[str]:
        values = []
        for k, v in content.items():
            k = tag("le", f'"{k}"' if isinstance(k, str) else k)
            v = adapt_value(v)
            if isinstance(v, str):
                v = tag("y", '"%s"' % v.replace("\n", "\\n"))
            elif isinstance(v, (dict, list)):
                v = pretty_view(v, _indent=_indent + 1)
            else:
                v = tag("lc", v)
            values.append(f"{k}: {v}")
        return values

    def list_(content: list) -> ty.List[str]:
        items = []
        for item in content:
            item = adapt_value(item)
            if isinstance(item, str):
                items.append(tag("y", f'"{item}"'))
            elif isinstance(item, (dict, list)):
                items.append(pretty_view(item, _indent=_indent + 1))
            else:
                items.append(tag("lc", item))
        return items

    result = ""

    if isinstance(data, dict):
        if len(data) > 2 or not all(
            isinstance(x, (str, int, float, bool)) or x is None for x in data.values()
        ):
            result = (
                "{\n"
                + "    " * (_indent + 1)
                + f",\n{'    ' * (_indent + 1)}".join(dict_(data))
                + "\n"
                + "    " * _indent
                + "}"
            )
        else:
            result = "{" + ", ".join(dict_(data)) + "}"
    elif isinstance(data, list):
        if len(data) > 15 or not all(
            isinstance(x, (str, int, float, bool)) for x in data
        ):
            result = (
                "[\n"
                + "    " * (_indent + 1)
                + f",\n{'    ' * (_indent + 1)}".join(list_(data))
                + "\n"
                + "    " * _indent
                + "]"
            )
        else:
            result = "[" + ", ".join(list_(data)) + "]"

    return tag("w", result)


def debug_book_data(book: Books | Book) -> str:
    data = {k: v for k, v in book.__dict__.items() if not k.startswith("_")}
    if "items" in data:
        data["items"] = f"<list ({len(data['items'])} objects)>"
    if "files" in data:
        data["files"] = f"<list ({len(data['files'])} objects)>"
    if len(data.get("description") or "") > 100:
        data["description"] = data["description"][:100] + "..."

    return "Book data: " + pretty_view(data)


def trace_book_data(book: Books | Book) -> str:
    return "Book data: " + pretty_view(
        {k: v for k, v in book.__dict__.items() if not k.startswith("_")}
    )


def send_system_notification(title: str, message: str = "") -> None:
    notification.notify(
        title=title,
        message=message,
        app_name="AB Player",
        ticker="AB Player",
        app_icon=os.path.join(os.environ["APP_DIR"], "icon.ico"),
    )

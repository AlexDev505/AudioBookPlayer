"""

Функции и классы, которые используются в приложении.

"""

from __future__ import annotations

import hashlib
import json
import threading
import typing as ty
from abc import abstractmethod

import pygments.formatters
import pygments.lexers
from PyQt5.QtCore import QObject, QThread

if ty.TYPE_CHECKING:
    from pathlib import Path


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


def convert_into_bits(bits: int) -> str:
    """
    :param bits: Число битов.
    :return: Строка вида <Число> <Единица измерения>
    """
    postfixes = ["КБ", "МБ", "ГБ"]
    if bits >= 2 ** 33:
        return f"{round(bits / 2 ** 33, 3)} {postfixes[-1]}"
    elif bits >= 2 ** 23:
        return f"{round(bits / 2 ** 23, 2)} {postfixes[-2]}"
    elif bits >= 2 ** 13:
        return f"{round(bits / 2 ** 13, 1)} {postfixes[-3]}"


def get_file_hash(file_path: ty.Union[str, Path], hash_func=hashlib.sha256) -> str:
    """
    :param file_path: Путь к файлу.
    :param hash_func: Функция хеширования.
    :return: Хеш файла.
    """
    hash_func = hash_func()
    with open(file_path, "rb") as file:
        for block in iter(lambda: file.read(65536), b""):
            hash_func.update(block)
    return hash_func.hexdigest()


def prepare_data(data: ty.Any) -> ty.Any:
    if isinstance(data, dict):
        return {k: prepare_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [prepare_data(obj) for obj in data]
    elif isinstance(data, bool):
        return str(data).lower()
    elif data is None:
        return "null"
    elif isinstance(data, (int, float, str)):
        return data
    else:
        if data.__repr__().startswith("{"):
            return data.__dict__
        return f'"{str(data)}"'


def pretty_view(data: ty.Union[dict, list], colorize=True) -> str:
    """
    Преобразовывает `data` в более удобный для восприятия вид.
    """
    data = prepare_data(data)
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False, indent=4)
    elif isinstance(data, list):
        data = ",\n".join(f"    {line}" for line in data)
        data = f"[\n{data}\n]"

    if colorize:
        return pygments.highlight(
            data,
            pygments.lexers.JsonLexer(),  # noqa
            pygments.formatters.TerminalFormatter(bg="light"),  # noqa
        ).rstrip()
    return data

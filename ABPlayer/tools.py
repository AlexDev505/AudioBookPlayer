"""

Функции и классы, которые используются в приложении.

"""

import os
import typing as ty
from abc import abstractmethod
from datetime import datetime

from PyQt5.QtCore import QObject, QThread


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
        self = super(BaseWorker, cls).__new__(cls, *args, **kwargs)
        self.__init__(*args, **kwargs)
        self.thread = QThread()  # Создаем новый поток
        self.moveToThread(self.thread)
        self.thread.started.connect(self.worker)
        return self

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


def debug(message: ty.Union[str, ty.List[str]]) -> None:
    """
    # TODO: Использовать loguru.
    Добавляет запись в файл отладки.
    :param message: Сообщение.
    """
    if isinstance(message, str):
        message = message.splitlines()

    with open(os.environ["DEBUG_PATH"], "a+") as file:
        title = (
            f"\n\n{datetime.now().strftime('%d.%m.%Y-%H:%M:%S')} "
            f"v: {os.environ['VERSION']}\n"
        )
        file.writelines([title] + message)

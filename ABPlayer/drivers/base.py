from __future__ import annotations

import typing as ty
from abc import ABC, abstractmethod
from enum import Enum

import requests

from .tools import NotImplementedVariable


if ty.TYPE_CHECKING:
    from pathlib import Path
    from models.book import Book


class DownloadProcessStatus(Enum):
    """
    Статусы прогресса скачивания.
    """

    WAITING = "waiting"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    FINISHED = "finished"


class BaseDownloadProcessHandler(ABC):
    """
    Обработчик процесса скачивания.
    Визуализирует процесс скачивания книги.
    >>> N = 10
    >>> process_handler = BaseDownloadProcessHandler()
    >>> process_handler.init(N, status=DownloadProcessStatus.DOWNLOADING)
    >>> for _ in range(N):
    >>>     process_handler.progress(1)
    >>> process_handler.finish()
    """

    def __init__(self):
        self.status = DownloadProcessStatus.WAITING
        self.total_size: int = ...
        self.done_size: int = ...

    def init(self, total_size: int, status: DownloadProcessStatus) -> None:
        self.status = status
        self.total_size = total_size
        self.done_size = 0

    def progress(self, size: int) -> None:
        self.done_size += size
        self.show_progress()

    def finish(self) -> None:
        self.status = DownloadProcessStatus.FINISHED
        self.done_size = self.total_size
        self.show_progress()

    @abstractmethod
    def show_progress(self) -> None:
        """
        Отображает прогресс.
        """


class BaseDownloader(ABC):
    """
    Загрузчик файлов.
    """

    def __init__(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ):
        self.book = book
        self.process_handler = process_handler

        # Общий размер файлов(в байтах)
        # Определяется, только если передан `process_handler`
        self.total_size: int | None = None

        self._file: ty.TextIO | None = None
        self._file_stream: requests.Response | None = None
        self._terminated: bool = False

    @abstractmethod
    def _prepare(self) -> None:
        """
        Подготавливает загрузчик к скачиванию.
        Должно быть переопределено в наследуемом классе.
        """

    @abstractmethod
    def _download_book(self) -> list[Path]:
        """
        Скачивает файлы.
        Должно быть переопределено в наследуемом классе.
        """

    def download_book(self) -> list[Path]:
        """
        Скачивает файлы книги.
        :returns: Список с путями к скачанным файлам.
        """
        self._prepare()
        return self._download_book()

    def terminate(self) -> None:
        """
        Прерывает загрузку.
        """
        self._terminated = True
        if self._file:
            if not self._file.closed:
                self._file.close()
        if self._file_stream:
            self._file_stream.close()


class Driver(ABC):
    drivers: list[ty.Type[Driver]] = []  # Все доступные драйверы

    site_url = NotImplementedVariable()
    downloader_factory = NotImplementedVariable()

    def __init__(self):
        self.downloader: BaseDownloader | None = None

    def __init_subclass__(cls, **kwargs):
        Driver.drivers.append(cls)

    @staticmethod
    def get_page(url: str) -> requests.Response:
        """
        :param url: Ссылка на книгу.
        :returns: Результат GET запроса.
        """
        return requests.get(url)

    @abstractmethod
    def get_book(self, url: str) -> Book:
        """
        Метод, получающий информацию о книге.
        Должен быть реализован для каждого драйвера отдельно.
        :param url: Ссылка на книгу.
        :returns: Экземпляр книги.
        """

    @abstractmethod
    def get_book_series(self, url: str) -> list[Book]:
        """
        Метод, получающий информацию о книгах из серии.
        Должен быть реализован для каждого драйвера отдельно.
        :param url: Ссылка на книгу.
        :returns: Список неполных экземпляров книг.
        """

    def download_book(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ) -> list[Path]:
        """
        Метод, скачивающий аудио файлы книги.
        :param book: Экземпляр книги.
        :param process_handler: Обработчик процесса скачивания.
        :return: Список путей к файлам.
        """
        self.downloader = self.downloader_factory(book, process_handler)
        return self.downloader.download_book()

    @classmethod
    @property
    def driver_name(cls) -> str:
        return cls.__name__

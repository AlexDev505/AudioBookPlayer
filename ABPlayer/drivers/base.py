from __future__ import annotations

import os
import shutil
import threading
import typing as ty
from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path

import requests
from loguru import logger

from .tools import NotImplementedVariable, create_instance_id, instance_id


if ty.TYPE_CHECKING:
    from models.book import Book


class DownloadProcessStatus(Enum):
    """
    Статусы прогресса скачивания.
    """

    WAITING = "waiting"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    FINISHING = "finishing"
    FINISHED = "finished"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


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
        create_instance_id(self)
        logger.opt(colors=True).trace(f"{self:styled} created")

    def init(self, total_size: int, status: DownloadProcessStatus) -> None:
        self.status = status
        self.total_size = total_size
        self.done_size = 0
        logger.opt(colors=True).trace(
            f"{self:styled} inited: "
            f"<y>{status.value}</y> total_size=<y>{total_size}</y>"
        )

    def progress(self, size: int) -> None:
        self.done_size += size
        self.show_progress()

    def finish(self) -> None:
        self.status = DownloadProcessStatus.FINISHED
        self.done_size = self.total_size
        logger.opt(colors=True).trace(f"{self:styled} finished")
        # self.show_progress()

    @abstractmethod
    def show_progress(self) -> None:
        """
        Отображает прогресс.
        """

    def __repr__(self):
        return f"DPH-{instance_id(self)}"

    def __format__(self, format_spec):
        if format_spec == "styled":
            return f"<y>{self!r}</y>"
        return repr(self)


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

        create_instance_id(self)
        threading.current_thread().name = repr(self)
        logger.opt(colors=True).debug(f"initialized. book: {book:styled}")

    @abstractmethod
    def _prepare(self) -> None:
        """
        Подготавливает загрузчик к скачиванию.
        Должно быть переопределено в наследуемом классе.
        """

    @abstractmethod
    def _download_book(self) -> None:
        """
        Скачивает файлы.
        Должно быть переопределено в наследуемом классе.
        """

    def save_preview(self) -> None:
        if self.book.preview:
            logger.opt(colors=True).debug(f"loading preview <y>{self.book.preview}</y>")
            try:
                response = requests.get(self.book.preview)
                if response.status_code == 200:
                    logger.trace("saving preview")
                    with open(self.book.preview_path, "wb") as file:
                        file.write(response.content)
                else:
                    logger.error(f"preview loading status: {response.status_code}")
            except IOError as err:
                logger.error(f"loading preview failed. {type(err).__name__}: {err}")

    def download_book(self) -> bool:
        """
        Скачивает файлы книги.
        :returns: Список с путями к скачанным файлам.
        """
        logger.debug("preparing downloading")
        self._prepare()
        logger.debug("downloading stared")
        self._download_book()
        if not self._terminated:
            if self.process_handler:
                self.process_handler.status = DownloadProcessStatus.FINISHING
            self.save_preview()
            self.book.save_to_storage()
            if self.process_handler:
                self.process_handler.finish()
                logger.debug("finished")
        else:
            if self.process_handler:
                self.process_handler.status = DownloadProcessStatus.TERMINATED
                logger.debug("terminated")
        return not self._terminated

    def terminate(self) -> None:
        """
        Прерывает загрузку.
        """
        logger.opt(colors=True).debug(f"<y>{self}</y> terminating")
        self.process_handler.status = DownloadProcessStatus.TERMINATING
        self._terminated = True
        if self._file:
            if not self._file.closed:
                logger.trace("closing file")
                self._file.close()
        if self._file_stream:
            logger.trace("closing file stream")
            self._file_stream.close()

        logger.opt(colors=True).debug(
            f"<y>{self}</y> clearing tree <y>{self.book.dir_path}</y>"
        )
        shutil.rmtree(self.book.dir_path, ignore_errors=True)
        os.removedirs(Path(self.book.dir_path).parent)

    def __repr__(self):
        return f"BookDownloader-{instance_id(self)}"


class Driver(ABC):
    drivers: list[ty.Type[Driver]] = []  # Все доступные драйверы

    site_url = NotImplementedVariable()
    downloader_factory = NotImplementedVariable()

    def __init__(self):
        self.downloader: BaseDownloader | None = None

    def __init_subclass__(cls, **kwargs):
        Driver.drivers.append(cls)

    @classmethod
    def get_suitable_driver(cls, url: str) -> ty.Type[Driver] | None:
        for driver in cls.drivers:
            if url.startswith(driver.site_url):
                return driver

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

    @abstractmethod
    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        """
        Метод, выполняющий поиск книг по запросу.
        Должен быть реализован для каждого драйвера отдельно.
        :param query: Поисковый запрос.
        :param limit: Кол-во книг, которое нужно вернуть.
        :param offset: Будет пропущено `offset` первых книг.
        :returns: Список неполных экземпляров книг.
        """

    def download_book(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ) -> bool:
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

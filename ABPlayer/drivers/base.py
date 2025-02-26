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
    Download progress statuses.
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
    Download process handler.
    Visualizes the book download process.
    >>> N = 10
    >>> process_handler = BaseDownloadProcessHandler()
    >>> process_handler.init(N, status=DownloadProcessStatus.DOWNLOADING)
    >>> for _ in range(N):
    ...     process_handler.progress(1)
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

    @abstractmethod
    def show_progress(self) -> None:
        """
        Displays progress.
        """

    def __repr__(self):
        return f"DPH-{instance_id(self)}"

    def __format__(self, format_spec):
        if format_spec == "styled":
            return f"<y>{self!r}</y>"
        return repr(self)


class BaseDownloader(ABC):
    """
    File downloader.
    """

    def __init__(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ):
        self.book = book
        self.process_handler = process_handler

        # Total file size (in bytes)
        # Determined only if `process_handler` is passed
        self.total_size: int | None = None

        # File opened for writing
        self._file: ty.TextIO | None = None
        # File download stream
        self._file_stream: requests.Response | None = None
        self._terminated: bool = False

        create_instance_id(self)
        threading.current_thread().name = repr(self)
        logger.opt(colors=True).debug(f"initialized. book: {book:styled}")

    @abstractmethod
    def _prepare(self) -> None:
        """
        Prepares the downloader for downloading.
        This method must be implemented in the inherited class.
        """

    @abstractmethod
    def _download_book(self) -> None:
        """
        Downloads files.
        This method must be implemented in the inherited class.
        """

    def save_preview(self) -> None:
        """
        Downloads and saves the book cover.
        """
        if not self.book.preview:
            return

        logger.opt(colors=True).debug(f"loading preview <y>{self.book.preview}</y>")
        try:
            response = requests.get(self.book.preview)
            if response.status_code == 200:
                logger.opt(colors=True).trace(
                    f"saving preview to <y>{self.book.preview_path}</y>"
                )
                with open(self.book.preview_path, "wb") as file:
                    file.write(response.content)
            else:
                logger.error(f"preview loading status: {response.status_code}")
        except IOError as err:
            logger.error(f"loading preview failed. {type(err).__name__}: {err}")

    def download_book(self) -> bool:
        """
        Downloads book files.
        :returns: List of paths to the downloaded files.
        """
        logger.debug("preparing downloading")
        self._prepare()
        logger.debug("downloading started")
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

        return not self._terminated  # True - if the download is successful

    def terminate(self) -> None:
        """
        Interrupts the download.
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
        try:
            os.removedirs(Path(self.book.dir_path).parent)
        except OSError:
            pass

    def __repr__(self):
        return f"BookDownloader-{instance_id(self)}"


class Driver(ABC):
    drivers: list[ty.Type[Driver]] = [] # All available drivers

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
        :param url: Link to the book.
        :returns: Result of the GET request.
        """
        return requests.get(url)

    @abstractmethod
    def get_book(self, url: str) -> Book:
        """
        Method to get information about the book.
        Must be implemented separately for each driver.
        :param url: Link to the book.
        :returns: Book instance.
        """

    @abstractmethod
    def get_book_series(self, url: str) -> list[Book]:
        """
        Method to get information about books in a series.
        Must be implemented separately for each driver.
        :param url: Link to the book.
        :returns: List of incomplete book instances.
        """

    @abstractmethod
    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        """
        Method to search for books by query.
        Must be implemented separately for each driver.
        :param query: Search query.
        :param limit: Number of books to return.
        :param offset: The first `offset` books will be skipped.
        :returns: List of incomplete book instances.
        """

    def download_book(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ) -> bool:
        """
        Method to download the book's audio files.
        :param book: Book instance.
        :param process_handler: Download process handler.
        :return: List of file paths.
        """
        self.downloader = self.downloader_factory(book, process_handler)
        return self.downloader.download_book()

    @classmethod
    @property
    def driver_name(cls) -> str:
        return cls.__name__


from __future__ import annotations

import asyncio
import os
import re
import shutil
import typing as ty
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import aiofiles
import aiohttp
import requests
from loguru import logger
from models.book import BookFiles
from tools import convert_from_bytes, get_file_hash

from .tools import (
    IOTasksManager,
    NotImplementedVariable,
    create_instance_id,
    instance_id,
    prepare_file_metadata,
)

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
        Displays the progress.
        """

    def __repr__(self):
        return f"DPH-{instance_id(self)}"

    def __format__(self, format_spec):
        if format_spec == "styled":
            return f"<y>{self!r}</y>"
        return repr(self)


@dataclass
class File:
    index: int
    name: str
    url: str
    duration: float | None = None
    size: int | None = None
    extra: dict = field(default_factory=dict)


class BaseDownloader(ABC):
    """
    File downloader.
    """

    def __init__(
        self,
        book: Book,
        process_handler: BaseDownloadProcessHandler | None = None,
    ):
        self.book = book
        self.downloaded_files: dict[int, Path] = {}
        self.process_handler = process_handler
        self.tasks_manager = IOTasksManager(20)
        self._session: aiohttp.ClientSession | None = None

        self._files: list[File] = []
        # Total size of files (in bytes)
        # Determined only if `process_handler` is passed
        self.total_size: int | None = None

        self._terminated: bool = False

        create_instance_id(self)
        logger.opt(colors=True).debug(
            f"{self!r} initialized. book: {book:styled}"
        )

    @abstractmethod
    def _prepare_files_data(self) -> list[File]:
        """
        Prepares files data: file names and urls.
        This method must be implemented in the subclass.
        """

    async def download_book(self) -> bool:
        """
        Downloads book files.
        :returns: True - if the download was successful
        """
        self._session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(sock_read=240)
        )
        logger.debug("preparing downloading")
        await self._prepare()
        if not self._terminated:
            logger.debug("downloading started")
            if self.process_handler:
                self.process_handler.init(
                    self.total_size, status=DownloadProcessStatus.DOWNLOADING
                )
            await self._download_files()
        if not self._terminated:
            logger.debug("finishing downloading")
            if self.process_handler:
                self.process_handler.status = DownloadProcessStatus.FINISHING
            await self._finish()

        if self._terminated:
            if self.process_handler:
                self.process_handler.status = DownloadProcessStatus.TERMINATED
            logger.debug("terminated")

        await self._session.close()
        self._session = None
        return not self._terminated

    async def _prepare(self) -> None:
        """
        Prepares the downloader for downloading.
        """
        self._files = self._prepare_files_data()
        if self.process_handler:
            self.total_size = 0
            # Инициализируем прогресс подготовки
            self.process_handler.init(
                len(self._files), status=DownloadProcessStatus.PREPARING
            )
            await self._calc_total_size()

    async def _calc_total_size(self) -> None:
        """
        Calculates the total size of the files.
        """
        await self.tasks_manager.wait_finishing(
            (self._add_file_size(file) for file in self._files)
        )

    async def _add_file_size(self, file: File) -> None:
        """
        Gets and adds size of file.
        """
        assert self._session is not None
        if self._terminated:
            return
        if not file.size:
            try:
                async with self._session.get(
                    file.url, headers=file.extra.get("headers")
                ) as response:
                    if not (
                        file_size := response.headers.get("content-length")
                    ):
                        raise RuntimeError("No content-length found")
                    file.size = int(file_size)
            except Exception as err:
                logger.opt(colors=True).debug(
                    f"getting file size failed {type(err).__name__}: {err}. retrying"
                )
                await asyncio.sleep(1)
                return await self._add_file_size(file)
        self.total_size += file.size
        self.process_handler.progress(1)

    async def _download_files(self) -> None:
        """
        Downloads files.
        """
        if not (book_dir_path := Path(self.book.dir_path)).exists():
            book_dir_path.mkdir(parents=True, exist_ok=True)
            logger.opt(colors=True).debug(
                f"book dir <y>{self.book.dir_path}</y> crated"
            )

        await self.tasks_manager.wait_finishing(
            (self._download_file(file) for file in self._files)
        )

    async def _download_file(self, file: File) -> None:
        """
        Downloads one file.
        """
        file_path = Path(os.path.join(self.book.dir_path, file.name))
        logger.opt(colors=True).trace(
            f"downloading file <y>{file.index}</y> <y>{file_path}</y> {file.url}"
        )

        async with aiofiles.open(file_path, mode="wb") as file_io:
            downloaded_size = 0
            while not self._terminated:
                try:
                    async for chunk in self._iter_chunks(file, downloaded_size):
                        if self._terminated:
                            return
                        if self.process_handler:
                            self.process_handler.progress(len(chunk))
                        downloaded_size += len(chunk)
                        await file_io.write(chunk)
                        await file_io.flush()
                    if file.size and downloaded_size < file.size:
                        raise RuntimeError(
                            "downloaded size lower than file size"
                        )
                    break
                except Exception as err:
                    if isinstance(err, aiohttp.ClientPayloadError):
                        continue
                    logger.opt(colors=True).debug(
                        f"downloading failed {type(err).__name__}: {err}"
                    )
                    await asyncio.sleep(5)
                    logger.opt(colors=True).trace(
                        f"retrying download file <y>{file.index}</y>"
                    )
        self.downloaded_files[file.index] = file_path
        await self._file_downloaded(file, file_path)

    async def _iter_chunks(
        self, file: File, offset: int = 0
    ) -> ty.AsyncGenerator[bytes]:
        """
        Iterates over the bytes chunks.
        """
        assert self._session is not None
        async with self._session.get(
            file.url,
            headers={
                "Range": f"bytes={offset}-",
                **file.extra.get("headers", {}),
            },
        ) as response:
            logger.opt(colors=True).trace(
                "{}: <y>{}</y>".format(
                    file.url,
                    convert_from_bytes(
                        int(response.headers.get("content-length"))
                    ),
                )
            )
            async for chunk in response.content.iter_chunked(5120):
                yield chunk

    async def _file_downloaded(self, file: File, file_path: Path) -> None:
        """
        Called when a file is downloaded.
        """

    async def _finish(self) -> None:
        """
        Finalizes downloading.
        Prepare files metadata and hashes, downloads preview, saves `.abp` file.
        """
        files = BookFiles()
        for i, item in enumerate(self.book.items):
            if self._terminated:
                return
            file_path = self.downloaded_files[i]
            logger.trace(f"preparing file metadata {file_path}")
            prepare_file_metadata(file_path, self.book.author, item.title, i)
            logger.trace(f"hashing file {file_path}")
            files[file_path.name] = get_file_hash(file_path)
        self.book.files = files
        await self.save_preview()
        self.book.save_to_storage()
        if self.process_handler:
            self.process_handler.finish()
        logger.debug("finished")

    async def save_preview(self) -> None:
        """
        Downloads and saves the book cover.
        """
        if not self.book.preview:
            return

        logger.opt(colors=True).debug(
            f"loading preview <y>{self.book.preview}</y>"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.book.preview) as response:
                    if response.status == 200:
                        logger.opt(colors=True).trace(
                            f"saving preview to <y>{self.book.preview_path}</y>"
                        )
                        async with aiofiles.open(
                            self.book.preview_path, mode="wb"
                        ) as file_io:
                            await file_io.write(await response.read())
                    else:
                        logger.error(
                            f"preview loading status: {response.status}"
                        )
        except IOError as err:
            logger.error(f"loading preview failed. {type(err).__name__}: {err}")

    async def terminate(self) -> None:
        """
        Interrupts loading.
        """
        logger.opt(colors=True).debug(f"<y>{self}</y> terminating")
        self.process_handler.status = DownloadProcessStatus.TERMINATING
        self._terminated = True
        await self.tasks_manager.terminate()

        logger.opt(colors=True).debug(
            f"<y>{self}</y> clearing tree <y>{self.book.dir_path}</y>"
        )
        shutil.rmtree(self.book.dir_path, ignore_errors=True)
        try:
            os.removedirs(Path(self.book.dir_path).parent)
        except OSError:
            pass

    def _get_item_file_name(
        self, item_index: int, extension: str = ".mp3"
    ) -> str:
        item = self.book.items[item_index]
        # Removes series_number from capture name
        item_title = re.sub(r"^(\d+) (.+)", r"\g<2>", item.title)
        if item_title.endswith(".wav"):
            extension = ""
        return f"{str(item_index + 1).rjust(2, '0')}. {item_title}{extension}"

    def __repr__(self):
        return f"BookDownloader-{instance_id(self)}"


class Driver(ABC):
    drivers: list[ty.Type[Driver]] = []  # All available drivers

    site_url: str = NotImplementedVariable()  # type: ignore
    downloader_factory: ty.Type[BaseDownloader] = NotImplementedVariable()  # type: ignore

    def __init__(self):
        self.downloader: BaseDownloader | None = None

    def __init_subclass__(cls, **kwargs):
        if ABC not in cls.__bases__:
            Driver.drivers.append(cls)

    @classmethod
    def get_suitable_driver(cls, url: str) -> ty.Type[Driver] | None:
        for driver in cls.drivers:
            if url.startswith(driver.site_url):
                return driver

    @staticmethod
    def get_page(url: str) -> requests.Response:
        """
        :param url: URL of the book.
        :returns: Result of the GET request.
        """
        return requests.get(url)

    @abstractmethod
    def get_book(self, url: str) -> Book:
        """
        Method that retrieves information about a book.
        Must be implemented for each driver separately.
        :param url: URL of the book.
        :returns: Instance of the book.
        """

    @abstractmethod
    def get_book_series(self, url: str) -> list[Book]:
        """
        Method that retrieves information about books in a series.
        Must be implemented for each driver separately.
        :param url: URL of the book.
        :returns: List of incomplete book instances.
        """

    @abstractmethod
    def search_books(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> list[Book]:
        """
        Method that performs a search for books by query.
        Must be implemented for each driver separately.
        :param query: Search query.
        :param limit: Number of books to return.
        :param offset: Number of books to skip from the start.
        :returns: List of incomplete book instances.
        """

    @classmethod
    @property
    def driver_name(cls) -> str:
        return cls.__name__


class LicensedDriver(Driver, ABC):
    AUTH_FILE: str
    is_authed: bool = False

    def __init_subclass__(cls, **kwargs):
        cls.AUTH_FILE = os.path.join(
            os.environ["AUTH_DIR"], f"{cls.driver_name}.dat"
        )
        super().__init_subclass__(**kwargs)

    @classmethod
    def auth(cls) -> bool:
        if not cls._auth():
            return False
        cls.is_authed = True
        return True

    @classmethod
    def auth_from_storage(cls) -> bool:
        if not cls._load_auth():
            return False
        cls.is_authed = True
        return True

    @classmethod
    @abstractmethod
    def _load_auth(cls) -> bool: ...

    @classmethod
    @abstractmethod
    def _auth(cls) -> bool: ...

    @classmethod
    def logout(cls) -> None:
        cls.is_authed = False
        if os.path.exists(cls.AUTH_FILE):
            os.remove(cls.AUTH_FILE)


class DriverNotAuthenticated(Exception):
    pass

from __future__ import annotations

import asyncio
import os
import re
import shutil
import typing as ty
from abc import ABC, abstractmethod
from contextlib import suppress
from dataclasses import dataclass, field
from enum import Enum
from functools import partial
from pathlib import Path

import aiofiles
import aiohttp
from loguru import logger

from models.book import AudioBook, TextBook
from tools import convert_from_bytes, get_file_hash

from .tools import (
    BaseProgressHandler,
    IOTasksManager,
    create_instance_id,
    instance_id,
    prepare_file_metadata,
)

if ty.TYPE_CHECKING:
    from models.book import BookSource, RawBook


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


class BaseDownloadingProgressHandler(
    BaseProgressHandler[DownloadProcessStatus], ABC
):
    DEFAULT_STATUS = DownloadProcessStatus.WAITING


@dataclass
class File:
    index: int
    name: str
    url: str
    size: int | None = None
    extra: dict = field(default_factory=dict)


class BaseDownloader[SourceT: BookSource](ABC):
    """
    File downloader.
    """

    def __init__(
        self,
        book: RawBook[SourceT],
        process_handler: BaseDownloadingProgressHandler,
    ):
        self._book = book
        self._downloaded_files: dict[int, Path] = {}
        self._process_handler = process_handler
        self._tasks_manager = IOTasksManager(20)
        self._session: aiohttp.ClientSession | None = None

        self._total_size = 0
        self._files: list[File] = []
        self._terminated: bool = False

        create_instance_id(self)
        logger.opt(colors=True).debug(
            f"{self!r} initialized. book: {self._book:colored}"
        )

    @property
    def process_handler(self) -> BaseDownloadingProgressHandler:
        return self._process_handler

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
            self._process_handler.init_status(
                DownloadProcessStatus.DOWNLOADING, self._total_size
            )
            await self._download_files()
        if not self._terminated:
            logger.debug("finishing downloading")
            self._process_handler.init_status(DownloadProcessStatus.FINISHING)
            await self._finish()

        if self._terminated:
            self._process_handler.init_status(DownloadProcessStatus.TERMINATED)
            logger.debug("terminated")

        await self._session.close()
        self._session = None
        return not self._terminated

    async def _prepare(self) -> None:
        """
        Prepares the downloader for downloading.
        """
        self._files = self._prepare_files_data()
        self._process_handler.init_status(
            DownloadProcessStatus.PREPARING, len(self._files)
        )
        await self._calc_total_size()

    async def _calc_total_size(self) -> None:
        """
        Calculates the total size of the files.
        """
        await self._tasks_manager.wait_finishing(
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
        self._total_size += file.size
        self._process_handler.progress(1)

    async def _download_files(self) -> None:
        """
        Downloads files.
        """
        if not (book_dir_path := Path(self._book.dir_path)).exists():
            book_dir_path.mkdir(parents=True, exist_ok=True)
            logger.opt(colors=True).debug(
                f"book dir <y>{self._book.dir_path}</y> created"
            )

        await self._tasks_manager.wait_finishing(
            (self._download_file(file) for file in self._files)
        )

    @logger.catch
    async def _download_file(self, file: File) -> None:
        """
        Downloads one file.
        """
        file_path = self._book.dir_path / file.name
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
                        self._process_handler.progress(chunk_size := len(chunk))
                        downloaded_size += chunk_size
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
                    logger.exception(err)
                    await asyncio.sleep(5)
                    logger.opt(colors=True).trace(
                        f"retrying download file <y>{file.index}</y>"
                    )
        self._downloaded_files[file.index] = file_path
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
            if content_length := response.headers.get("content-length"):
                logger.opt(colors=True, lazy=True).trace(
                    "{url}: <y>{size}</y>",
                    url=lambda file=file: file.url,
                    size=partial(convert_from_bytes, int(content_length)),
                )
            async for chunk in response.content.iter_chunked(64 * 1024):
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
        files = await asyncio.get_event_loop().run_in_executor(
            None, self._final_files, self._downloaded_files
        )
        if self._terminated:
            return
        self._book.source.files = files
        await self.save_cover()
        self._process_handler.init_status(DownloadProcessStatus.FINISHED)
        logger.debug("finished")

    def _final_files(self, downloaded_files: dict[int, Path]) -> dict[str, str]:
        files = dict[str, str]()
        for file_index in range(len(downloaded_files)):
            if self._terminated:
                return files
            file_path = downloaded_files[file_index]
            self._final_file(file_index, file_path, files)
        return files

    def _final_file(
        self, file_index: int, file_path: Path, files: dict[str, str]
    ) -> None:
        logger.trace(f"hashing file {file_path}")
        files[file_path.name] = get_file_hash(file_path)

    async def save_cover(self) -> None:
        """
        Downloads and saves the book cover.
        """
        if not self._book.source.cover:
            return

        logger.opt(colors=True).debug(
            f"loading cover <y>{self._book.source.cover}</y>"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self._book.source.cover) as response:
                    if response.status == 200:
                        cover_path = self._book.cover_path
                        logger.opt(colors=True).trace(
                            f"saving cover to <y>{cover_path}</y>"
                        )
                        async with aiofiles.open(
                            cover_path, mode="wb"
                        ) as file_io:
                            await file_io.write(await response.read())
                    else:
                        logger.error(f"cover loading status: {response.status}")
        except IOError as err:
            logger.error(f"loading cover failed. {type(err).__name__}: {err}")

    async def terminate(self) -> None:
        """
        Interrupts loading.
        """
        logger.opt(colors=True).debug(f"<y>{self!r}</y> terminating")
        self._process_handler.init_status(DownloadProcessStatus.TERMINATING)
        self._terminated = True
        await self._tasks_manager.terminate()
        await self._terminate()

        logger.opt(colors=True).debug(
            f"<y>{self}</y> clearing tree <y>{self._book.dir_path}</y>"
        )
        shutil.rmtree(self._book.dir_path, ignore_errors=True)
        with suppress(OSError):
            os.removedirs(Path(self._book.dir_path).parent)

    async def _terminate(self) -> None:
        pass

    def __repr__(self):
        return f"BookDownloader-{instance_id(self)}"


class BaseAudioDownloader(BaseDownloader[AudioBook], ABC):
    def _get_chapter_file_name(
        self, chapter_index: int, extension: str = ".mp3"
    ) -> str:
        item = self._book.source.chapters[chapter_index]
        # Removes series_number from chapter name
        chapter_title = re.sub(r"^(\d+) (.+)", r"\g<2>", item.title)
        if chapter_title.endswith(".wav"):
            extension = ""
        return f"{str(chapter_index + 1).rjust(2, '0')}. {chapter_title}{extension}"

    def _final_file(
        self, file_index: int, file_path: Path, files: dict[str, str]
    ) -> None:
        logger.trace(f"preparing file metadata {file_path}")
        prepare_file_metadata(
            file_path,
            file_index,
            self._book.author,
            self._book.title,
            self._book.series_name,
        )
        return super()._final_file(file_index, file_path, files)


class BaseTextDownloader(BaseDownloader[TextBook]):
    def _prepare_files_data(self):
        return [
            File(
                index=0,
                name=f"{self._book.author} — {self._book.title}"
                + (
                    f" ({self._book.source.publication})"
                    if self._book.source.publication
                    else ""
                ),
                url=self._book.source.file_url,
            )
        ]

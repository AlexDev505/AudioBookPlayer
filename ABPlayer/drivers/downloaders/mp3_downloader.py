from __future__ import annotations

import re
import time
import typing as ty
from contextlib import suppress
from pathlib import Path

import requests
from loguru import logger

from models.book import BookFiles
from ..base import BaseDownloader, DownloadProcessStatus
from ..tools import prepare_file_metadata
from tools import get_file_hash, convert_from_bytes


if ty.TYPE_CHECKING:
    from models.book import Book, BookItem
    from ..base import BaseDownloadProcessHandler


class MP3Downloader(BaseDownloader):
    """
    Loader designed for books where files are presented
    as separate or combined MP3 files.
    """

    def __init__(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ):
        super().__init__(book, process_handler)

        self._files_urls = []  # File URLs
        # True - if there is more than one chapter in a single audio file
        self.merged: bool = False

    def _prepare(self) -> None:
        if self.process_handler:
            self.total_size = 0
            # Initialize preparation progress
            self.process_handler.init(
                len(self.book.items), status=DownloadProcessStatus.PREPARING
            )

        for item in self.book.items:
            if self._terminated:
                break

            if self.process_handler:
                self.process_handler.progress(1)

            if (url := item.file_url) not in self._files_urls:
                self._files_urls.append(url)
                if self.process_handler:
                    # Determine file size
                    file_stream = requests.get(url, stream=True)
                    self.total_size += int(
                        file_stream.headers.get("content-length") or 0
                    )
                    file_stream.close()
            else:
                self.merged = True

    def _download_book(self) -> None:
        if self.process_handler:
            # Initialize download progress
            self.process_handler.init(
                self.total_size, status=DownloadProcessStatus.DOWNLOADING
            )

        files = BookFiles()
        for i, item in enumerate(self.book.items):
            if self._terminated:
                break

            if self.merged:
                if item.file_url not in self._files_urls:
                    continue
                # Exclude URL to avoid downloading the file again
                self._files_urls[item.file_index] = None

            file_path = self._get_file_path(item)
            if not file_path.parent.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
                logger.opt(colors=True).debug(
                    f"book dir <y>{file_path.parent}</y> crated"
                )

            logger.opt(colors=True).debug(f"downloading file <y>{i}</y>")
            while True:
                try:
                    if not self._terminated:
                        self._download_file(file_path, item.file_url)
                    break
                except requests.exceptions.RequestException as err:
                    logger.opt(colors=True).debug(
                        f"downloading failed {type(err).__name__}: {err}"
                    )
                    time.sleep(5)
                    logger.opt(colors=True).trace(f"retrying download file <y>{i}</y>")
            if self._terminated:
                break

            logger.trace("preparing file metadata")
            prepare_file_metadata(
                file_path,
                self.book.author,
                title=(
                    item.title
                    if not self.merged
                    else f"{self.book.author} - {self.book.name}"
                ),
                item_index=i if not self.merged else item.file_index,
            )
            logger.trace("hashing file")
            files[file_path.name] = get_file_hash(file_path)
        else:
            self.book.files = files

    def _get_file_path(self, item: BookItem) -> Path:
        item_title = (
            re.sub(r"^(\d+) (.+)", r"\g<2>", item.title)
            if not self.merged
            else f"{self.book.author} - {self.book.name}"
        )
        return Path(
            self.book.dir_path,
            f"{str(item.file_index + 1).rjust(2, '0')}. {item_title}.mp3",
        )

    def _download_file(self, file_path: Path, url: str) -> bool:
        logger.opt(colors=True).trace(f"file <y>{file_path}</y> {url}")

        self._file = open(file_path, "wb")
        self._file_stream = requests.get(url, timeout=10, stream=True)
        logger.opt(colors=True).trace(
            "file size: <y>{}</y>".format(
                content_length
                if (
                    content_length := self._file_stream.headers.get("content-length")
                ).isdigit()
                else convert_from_bytes(int(content_length))
            )
        )
        with suppress(requests.exceptions.StreamConsumedError):
            for data in self._file_stream.iter_content(chunk_size=5120):
                if self._terminated:
                    return False
                if self.process_handler:
                    self.process_handler.progress(len(data))
                self._file.write(data)
                self._file.flush()

            self._file_stream = None
            self._file.close()
            self._file = None

        return True


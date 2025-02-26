from __future__ import annotations

import binascii
import os
import re
import time
import typing as ty
from contextlib import suppress
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import m3u8
import requests
from Crypto.Cipher import AES
from loguru import logger

from models.book import BookFiles
from tools import get_file_hash, convert_from_bytes
from ..base import BaseDownloader, DownloadProcessStatus
from ..tools import prepare_file_metadata, get_audio_file_duration


if ty.TYPE_CHECKING:
    from models.book import Book
    from ..base import BaseDownloadProcessHandler


class M3U8Downloader(BaseDownloader):
    """
    Loader designed for books where files are presented with an m3u8 file.

    """

    def __init__(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ):
        super().__init__(book, process_handler)

        self._m3u8_data = None  # m3u8 object
        self._host_uri: str | None = None
        self._encryption_key: str | None = None  # Fragment encryption key

    def _prepare(self) -> None:
        self._m3u8_data = m3u8.load(self.book.items[0].file_url)
        self._parse_host_uri()

        if self.process_handler:
            # Total size of the book (in bytes)
            total_size = self._calc_total_size()
            self.process_handler.init(
                total_size, status=DownloadProcessStatus.DOWNLOADING
            )

    def _download_book(self) -> None:
        files = BookFiles()

        item_index = 0
        item = self.book.items[item_index]
        file_path = self._get_file_path(item_index)
        self._file = open(file_path, "wb")

        for segment_index, segment in enumerate(self._m3u8_data.segments):
            if self._terminated:
                break

            logger.opt(colors=True).debug(
                f"downloading segment <y>{segment_index}</y> "
                f"of item <y>{item_index}</y>"
            )
            while True:
                try:
                    if not self._terminated:
                        self._download_segment(segment_index, segment)
                    break
                except requests.exceptions.ConnectionError as err:
                    logger.opt(colors=True).debug(
                        f"downloading failed {type(err).__name__}: {err}"
                    )
                    time.sleep(5)
                    logger.opt(colors=True).trace(
                        f"retrying download segment <y>{segment_index}</y>"
                    )
            if self._terminated:
                break

            # If the duration of the resulting file is equal to the duration of the chapter
            # (tolerance of 2 seconds)
            if item.duration - get_audio_file_duration(file_path) < 2:
                logger.debug("item completed")
                self._file.close()
                self._file = None
                logger.trace("preparing file metadata")
                prepare_file_metadata(
                    file_path, self.book.author, item.title, item_index
                )
                logger.trace("hashing file")
                files[file_path.name] = get_file_hash(file_path)
                # Move to the next chapter
                if item_index + 1 < len(self.book.items):
                    item_index += 1
                    item = self.book.items[item_index]
                    file_path = self._get_file_path(item_index)
                    self._file = open(file_path, "wb")
        else:
            self.book.files = files

    def _download_segment(self, segment_index: int, segment):
        ts_url = os.path.join(self._host_uri, segment.uri)  # Segment URL
        logger.opt(colors=True).trace(f"segment <y>{segment.title}</y>({ts_url})")

        decrypt_func = self._get_decryption_func(segment_index, segment)

        # Create a fragment streaming loader object
        self._file_stream = requests.get(ts_url, timeout=10, stream=True)
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
                    break
                if self.process_handler:
                    self.process_handler.progress(len(data))
                # Add fragment to audio file
                self._file.write(data if not decrypt_func else decrypt_func(data))
                # Flush data to file. Free up memory
                self._file.flush()
        self._file_stream = None

    def _get_decryption_func(self, segment_index: int, segment):
        # Define fragment decryption function
        decrypt_func = None
        if segment.key.method == "AES-128":
            if not self._encryption_key:
                key_uri = segment.key.uri
                self._encryption_key = urlopen(key_uri).read()

            ind = segment_index + self._m3u8_data.media_sequence
            iv = binascii.a2b_hex("%032x" % ind)
            cipher = AES.new(self._encryption_key, AES.MODE_CBC, iv=iv)
            decrypt_func = cipher.decrypt

        return decrypt_func

    def _parse_host_uri(self) -> None:
        host_uri = urlparse(self.book.items[0].file_url)
        self._host_uri = (
            f"{host_uri.scheme}://{host_uri.hostname}"
            f"{host_uri.path[:host_uri.path.rfind('/')]}/"
        )

    def _calc_total_size(self) -> int:
        total_size = 0

        self.process_handler.init(
            len(self._m3u8_data.segments), status=DownloadProcessStatus.PREPARING
        )

        for i, segment in enumerate(self._m3u8_data.segments):
            if self._terminated:
                break

            self.process_handler.progress(1)
            ts_url = urljoin(self._host_uri, segment.uri)
            file_stream = requests.get(ts_url, stream=True)
            total_size += int(file_stream.headers.get("content-length") or 0)
            file_stream.close()

        return total_size

    def _get_file_path(self, item_index: int) -> Path:
        item = self.book.items[item_index]
        # Remove file number from the name
        item_title = re.sub(r"^(\d+) (.+)", r"\g<2>", item.title)
        file_path = Path(
            os.path.join(
                self.book.dir_path,
                f"{str(item_index + 1).rjust(2, '0')}. {item_title}.mp3",
            )
        )
        if not file_path.parent.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            logger.opt(colors=True).debug(f"book dir <y>{file_path.parent}</y> crated")

        return file_path


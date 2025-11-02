from __future__ import annotations

import asyncio
import binascii
import os
import typing as ty
from functools import partial
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import aiofiles
import m3u8
from Crypto.Cipher import AES
from loguru import logger

from ..base import BaseDownloader, File
from ..tools import (
    convert_ts_to_mp3,
    get_audio_file_duration,
    merge_ts_files,
    split_ts,
)

if ty.TYPE_CHECKING:
    from models.book import Book

    from ..base import BaseDownloadProcessHandler


class MergedM3U8Downloader(BaseDownloader):
    """
    A loader designed for books in which files are presented in ONE M3U8 file.
    """

    def __init__(
        self,
        book: Book,
        process_handler: BaseDownloadProcessHandler | None = None,
    ):
        super().__init__(book, process_handler)

        self._m3u8_data = None  # Object m3u8
        self._host_uri: str | None = None
        self._encryption_key: str | None = (
            None  # The encryption key of fragments
        )

        self._next_seq_index: int = 0
        self._ts_file_paths: list[Path] = []
        self._current_duration: float = 0
        self._item_index: int = 0
        self._real_item_paths: list[Path] = []

    def _prepare_files_data(self):
        return [
            File(
                index=i,
                name=f"seq{i}.ts",
                url=urljoin(self._host_uri, segment.uri),
                duration=getattr(segment, "duration", None),
            )
            for i, segment in enumerate(self._m3u8_data.segments)
        ]

    async def _prepare(self):
        # loads m3u8 file
        self._m3u8_data = m3u8.load(self.book.items[0].file_url)
        self._parse_host_uri()
        await super()._prepare()

    async def _file_downloaded(self, file, file_path) -> None:
        await self._decrypt_seq(file)
        await self._seq_downloaded(file)

    async def _decrypt_seq(self, file: File) -> None:
        segment = self._m3u8_data.segments[file.index]
        if decrypt_func := self._get_decryption_func(file.index, segment):
            file_path = os.path.join(self.book.dir_path, file.name)
            async with aiofiles.open(file_path, "rb") as f:
                data = await f.read()
            data = decrypt_func(data)
            async with aiofiles.open(file_path, "wb") as f:
                await f.write(data)

    async def _seq_downloaded(self, file: File) -> None:
        if file.index != self._next_seq_index or not (
            ts_path := self.downloaded_files.get(file.index)
        ):
            return
        self._ts_file_paths.append(ts_path)
        if self._item_index + 1 == len(self.book.items):
            self._next_seq_index += 1
            if self._next_seq_index == len(self._files):
                return
            return await self._seq_downloaded(self._files[self._next_seq_index])
        item = self.book.items[self._item_index]
        ts_duration = file.duration or get_audio_file_duration(ts_path)
        self._current_duration += ts_duration
        if item.duration - self._current_duration < 0.5:
            second = second_time = 0
            split_time = round(
                item.duration - (self._current_duration - ts_duration)
            )
            second_time = ts_duration - split_time
            if item.duration - self._current_duration < 0 and second_time > 1:
                first, second = split_ts(ts_path, split_time)
                self._ts_file_paths.remove(ts_path)
                self._ts_file_paths.append(first)
                os.remove(ts_path)
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                partial(
                    self._merge_ts_files,
                    int(self._item_index),
                    self._ts_file_paths.copy(),
                ),
            )
            self._current_duration = second_time
            self._ts_file_paths.clear()
            if second:
                self._ts_file_paths.append(second)
            self._item_index += 1
        self._next_seq_index += 1
        await self._seq_downloaded(self._files[self._next_seq_index])

    async def _finish(self) -> None:
        if self._ts_file_paths:
            self._merge_ts_files(self._item_index, self._ts_file_paths)
        self.downloaded_files = dict(enumerate(self._real_item_paths))
        await super()._finish()

    def _merge_ts_files(
        self, item_index: int, ts_file_paths: list[Path]
    ) -> None:
        item_file_name = self._get_item_file_name(item_index, "")
        logger.opt(colors=True).debug(
            f"merging <y>{len(ts_file_paths)}</y> files to <y>{item_file_name}.mp3</y>"
        )
        merge_ts_files(ts_file_paths, Path(self.book.dir_path), item_file_name)
        logger.trace(f"deleting {len(ts_file_paths)} ts files")
        for ts_path in ts_file_paths:
            os.remove(ts_path)
        logger.opt(colors=True).debug(
            f"file <y>{item_file_name}.mp3</y> created"
        )
        self._real_item_paths.append(
            Path(self.book.dir_path, item_file_name + ".mp3")
        )

    def _get_decryption_func(
        self, segment_index: int, segment
    ) -> ty.Callable[[bytes], bytes] | None:
        # Determine the function of decryption of the fragment
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
            f"{host_uri.path[: host_uri.path.rfind('/')]}/"
        )

from __future__ import annotations

import asyncio
import binascii
import os
import subprocess
import typing as ty
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import m3u8
from Crypto.Cipher import AES
from loguru import logger

from ..base import BaseDownloader
from ..tools import get_audio_file_duration


if ty.TYPE_CHECKING:
    from models.book import Book
    from ..base import BaseDownloadProcessHandler


def merge_ts_files(ts_file_paths: list[Path], output_file_path: Path) -> None:
    """
    Merges ts files to one.
    """
    result = subprocess.check_output(
        f'copy /b {"+".join(map(lambda x: x.name, ts_file_paths))} '
        f'"{output_file_path}"',
        cwd=output_file_path.parent,
        shell=True,
        stderr=subprocess.STDOUT,
    ).decode("cp866")
    if result:
        logger.debug(result)


def convert_ts_to_mp3(ts_file_path: Path, mp3_file_path: Path) -> None:
    """
    Converts ts files to mp3 by ffmpeg.
    """
    subprocess.check_output(
        f'{os.environ["FFMPEG_PATH"]} -y -v quiet -i "{ts_file_path}" -vn '
        f'"{mp3_file_path}"',
        stderr=subprocess.STDOUT,
    )


def split_ts(ts_file_path: Path, on: int) -> tuple[Path, Path]:
    first_part = Path(
        os.path.join(
            ts_file_path.parent, f"{ts_file_path.name.removesuffix(".ts")}-1.ts"
        )
    )
    second_part = Path(
        os.path.join(
            ts_file_path.parent, f"{ts_file_path.name.removesuffix(".ts")}-2.ts"
        )
    )
    subprocess.check_output(
        f'{os.environ["FFMPEG_PATH"]} -i "{ts_file_path}" -to {on} -c copy '
        f'"{first_part}"',
        stderr=subprocess.STDOUT,
    )
    subprocess.check_output(
        f'{os.environ["FFMPEG_PATH"]} -i "{ts_file_path}" -ss {on} -c copy '
        f'"{second_part}"',
        stderr=subprocess.STDOUT,
    )
    return first_part, second_part


class M3U8Downloader(BaseDownloader):
    """
    Загрузчик, предназначенный для книг в которых файлы представлены
    m3u8 файлом.
    """

    def __init__(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ):
        super().__init__(book, process_handler)

        self._m3u8_data = None  # Объект m3u8
        self._host_uri: str | None = None
        self._encryption_key: str | None = None  # Ключ шифрования фрагментов

        self._next_seq_index: int = 0
        self._ts_file_paths: list[Path] = []
        self._current_duration: float = 0
        self._item_index: int = 0
        self._real_item_paths: list[Path] = []

    def _prepare_files_data(self):
        return [
            (f"seq{i}.ts", urljoin(self._host_uri, segment.uri))
            for i, segment in enumerate(self._m3u8_data.segments)
        ]

    def _prepare(self):
        # loads m3u8 file
        self._m3u8_data = m3u8.load(self.book.items[0].file_url)
        self._parse_host_uri()
        super()._prepare()

    async def _download_file(
        self, file_index: int, file_url: str, file_name: str
    ) -> None:
        await super()._download_file(file_index, file_url, file_name)
        self._seq_downloaded(file_index)

    def _seq_downloaded(self, seq_index: int) -> None:
        if seq_index != self._next_seq_index or not (
            ts_path := self.downloaded_files.get(seq_index)
        ):
            return
        item = self.book.items[self._item_index]
        self._ts_file_paths.append(ts_path)
        ts_duration = get_audio_file_duration(ts_path)
        self._current_duration += ts_duration
        if item.duration - self._current_duration < 2:
            second = second_time = 0
            if self._current_duration - item.duration > 2:
                split_time = round(
                    item.duration - (self._current_duration - ts_duration)
                )
                first, second = split_ts(ts_path, split_time)
                second_time = ts_duration - split_time
                self._ts_file_paths.remove(ts_path)
                self._ts_file_paths.append(first)
                os.remove(ts_path)
            loop = asyncio.get_event_loop()
            loop.run_in_executor(
                None,
                self._merge_ts_files,
                int(self._item_index),
                self._ts_file_paths.copy(),
            )
            self._current_duration = second_time
            self._ts_file_paths.clear()
            if second:
                self._ts_file_paths.append(second)
            self._item_index += 1
        self._next_seq_index += 1
        self._seq_downloaded(self._next_seq_index)

    async def _iter_chunks(self, file_url, offset=0):
        segment_index = self._files.index(
            next(filter(lambda x: x[1] == file_url, self._files))
        )
        segment = self._m3u8_data.segments[segment_index]
        decrypt_func = self._get_decryption_func(segment_index, segment)
        # getting full file for correctly decryption
        data = bytearray()
        async for chunk in super()._iter_chunks(file_url):
            data.extend(chunk)
        yield data if not decrypt_func else decrypt_func(data)

    def _finish(self) -> None:
        if self._ts_file_paths:
            self._merge_ts_files(self._item_index, self._ts_file_paths)
        self.downloaded_files = dict(enumerate(self._real_item_paths))
        super()._finish()

    def _merge_ts_files(self, item_index: int, ts_file_paths: list[Path]) -> None:
        item_file_path = os.path.join(
            self.book.dir_path,
            self._get_item_file_name(item_index).removesuffix(".mp3"),
        )
        ts_item_fp = Path(f"{item_file_path}.ts")
        mp3_item_fp = Path(f"{item_file_path}.mp3")
        logger.opt(colors=True).debug(
            f"merging <y>{len(ts_file_paths)}</y> files to <y>{ts_item_fp}</y>"
        )
        merge_ts_files(ts_file_paths, ts_item_fp)
        logger.trace(f"deleting {len(ts_file_paths)} ts files")
        for ts_path in ts_file_paths:
            os.remove(ts_path)
        logger.opt(colors=True).trace(
            f"converting <y>{ts_item_fp}</y> to <y>{mp3_item_fp}</y>"
        )
        convert_ts_to_mp3(ts_item_fp, mp3_item_fp)
        logger.trace(f"deleting {ts_item_fp}")
        os.remove(ts_item_fp)
        logger.opt(colors=True).debug(f"file <y>{mp3_item_fp}</y> created")
        self._real_item_paths.append(mp3_item_fp)

    def _get_decryption_func(self, segment_index: int, segment):
        # Определяем функцию дешифрования фрагмента
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

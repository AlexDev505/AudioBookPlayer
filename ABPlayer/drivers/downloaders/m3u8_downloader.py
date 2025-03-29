from __future__ import annotations

import binascii
import os
import subprocess
import typing as ty
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import m3u8
from Crypto.Cipher import AES

from ..base import BaseDownloader
from ..tools import get_audio_file_duration


if ty.TYPE_CHECKING:
    from models.book import Book, BookItem
    from ..base import BaseDownloadProcessHandler


def merge_ts_files(ts_file_paths: list[Path], output_file_path: Path) -> None:
    """
    Merges ts files to one.
    """
    os.system(
        f'copy /b {"+".join(map(lambda x: f'"{x}"', ts_file_paths))} '
        f'"{output_file_path}"'
    )


def convert_ts_to_mp3(ts_file_path: Path, mp3_file_path: Path) -> None:
    """
    Converts ts files to mp3 by ffmpeg.
    """
    subprocess.check_output(
        f'{os.environ["FFMPEG_PATH"]} -y -v quiet -i "{ts_file_path}" -vn '
        f'"{mp3_file_path}"',
        stderr=subprocess.STDOUT,
    )


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
        # Merging ts files and converting they to mp3 files
        ts_files = [
            self.downloaded_files[i] for i in sorted(self.downloaded_files.keys())
        ]
        self.downloaded_files = {}
        for item_index, item in enumerate(self.book.items):
            tss_duration = 0
            for i in range(len(ts_files)):
                tss_duration += get_audio_file_duration(ts_files[i])
                # Если общая длительность сегментов равна длительности главы
                # (погрешность 2 сек)
                if item.duration - tss_duration < 2:
                    item_file_path = self._merge_ts_files(item, ts_files[: i + 1])
                    ts_files = ts_files[i + 1 :]
                    break
            else:
                item_file_path = self._merge_ts_files(item, ts_files)
            self.downloaded_files[item_index] = item_file_path
        super()._finish()

    def _merge_ts_files(self, item: BookItem, ts_file_paths: list[Path]) -> Path:
        item_file_path = os.path.join(
            self.book.dir_path, self._get_item_file_name(item).removesuffix(".mp3")
        )
        ts_item_fp = Path(f"{item_file_path}.ts")
        mp3_item_fp = Path(f"{item_file_path}.mp3")
        merge_ts_files(ts_file_paths, ts_item_fp)
        for ts_path in ts_file_paths:
            os.remove(ts_path)
        convert_ts_to_mp3(ts_item_fp, mp3_item_fp)
        os.remove(ts_item_fp)
        return mp3_item_fp

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

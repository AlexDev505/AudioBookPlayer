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


def merge_ts_files(ts_file_paths: list[Path], output_file_path: Path) -> None:
    os.system(
        f'copy /b {"+".join(map(lambda x: f'"{x}"', ts_file_paths))} '
        f'"{output_file_path}"'
    )


def convert_ts_to_mp3(ts_file_path: Path, mp3_file_path: Path) -> None:
    os.system(
        f'{os.environ["FFMPEG_PATH"]} -v quiet -i "{ts_file_path}" -vn '
        f'"{mp3_file_path}"'
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

    def _prepare(self) -> None:
        self._m3u8_data = m3u8.load(self.book.items[0].file_url)
        self._parse_host_uri()

        if self.process_handler:
            # Общий размер книги(в байтах)
            total_size = self._calc_total_size()
            self.process_handler.init(
                total_size, status=DownloadProcessStatus.DOWNLOADING
            )

    def _download_book(self) -> None:
        files = BookFiles()

        if not (book_dir_path := Path(self.book.dir_path)).exists():
            book_dir_path.mkdir(parents=True, exist_ok=True)
            logger.opt(colors=True).debug(
                f"book dir <y>{self.book.dir_path}</y> crated"
            )

        ts_paths = []
        for segment_index, segment in enumerate(self._m3u8_data.segments):
            if self._terminated:
                break

            logger.opt(colors=True).debug(f"downloading segment <y>{segment_index}</y>")
            ts_path = Path(os.path.join(self.book.dir_path, f"seq{segment_index}.ts"))
            ts_paths.append(ts_path)
            self._file = open(ts_path, "wb")

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
            self._file.close()
            self.file = None

            if self._terminated:
                break
        else:
            self.process_handler.status = DownloadProcessStatus.FINISHING
            for item_index, item in enumerate(self.book.items):
                tss_duration = 0
                for i in range(len(ts_paths)):
                    tss_duration += get_audio_file_duration(ts_paths[i])
                    # Если общая длительность сегментов равна длительности главы
                    # (погрешность 2 сек)
                    if item.duration - tss_duration < 2:
                        item_file_path = self._merge_ts_files(
                            item_index, ts_paths[: i + 1]
                        )
                        ts_paths = ts_paths[i + 1 :]
                        break
                else:
                    item_file_path = self._merge_ts_files(item_index, ts_paths)
                logger.trace("preparing file metadata")
                prepare_file_metadata(
                    item_file_path, self.book.author, item.title, item_index
                )
                logger.trace("hashing file")
                files[item_file_path.name] = get_file_hash(item_file_path)
            self.book.files = files

    def _merge_ts_files(self, item_index: int, ts_file_paths: list[Path]) -> Path:
        item_file_path = self._get_file_path(item_index)
        ts_item_fp = Path(f"{item_file_path}.ts")
        mp3_item_fp = Path(f"{item_file_path}.mp3")
        merge_ts_files(ts_file_paths, ts_item_fp)
        for ts_path in ts_file_paths:
            os.remove(ts_path)
        convert_ts_to_mp3(ts_item_fp, mp3_item_fp)
        os.remove(ts_item_fp)
        return mp3_item_fp

    def _download_segment(self, segment_index: int, segment):
        ts_url = os.path.join(self._host_uri, segment.uri)  # Ссылка на сегмент
        logger.opt(colors=True).trace(f"segment <y>{segment.title}</y>({ts_url})")

        decrypt_func = self._get_decryption_func(segment_index, segment)

        # Создаем объект потоковой загрузки фрагмента
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
                # Добавляем фрагмент в аудио файл
                self._file.write(data if not decrypt_func else decrypt_func(data))
                # Сбрасываем данные в файл. Освобождаем память
                self._file.flush()
        self._file_stream = None

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
        # Убираем номер файла из названия
        item_title = re.sub(r"^(\d+) (.+)", r"\g<2>", item.title)
        file_path = Path(
            os.path.join(
                self.book.dir_path,
                f"{str(item_index + 1).rjust(2, '0')}. {item_title}",
            )
        )

        return file_path

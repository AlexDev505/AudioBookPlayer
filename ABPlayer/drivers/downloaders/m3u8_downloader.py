from __future__ import annotations

import binascii
import os
import re
import typing as ty
from contextlib import suppress
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen

import m3u8
import requests
from Crypto.Cipher import AES
from loguru import logger

from ..base import BaseDownloader, DownloadProcessStatus
from ..tools import prepare_file_metadata, get_audio_file_duration


if ty.TYPE_CHECKING:
    from models.book import Book
    from ..base import BaseDownloadProcessHandler


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

    def _prepare(self) -> None:
        self._m3u8_data = m3u8.load(self.book.items[0].file_url)
        self._parse_host_uri()

        if self.process_handler:
            # Общий размер книги(в байтах)
            total_size = self._calc_total_size()
            logger.opt(colors=True).debug(f"Total size: <y>{total_size} bytes</y>")
            self.process_handler.init(
                total_size, status=DownloadProcessStatus.DOWNLOADING
            )

    def _download_book(self) -> list[Path]:
        files: list[Path] = []  # Результат. Пути к скачанным файлам
        key = None  # Ключ шифрования фрагментов

        item_index = 0
        item = self.book.items[item_index]
        file_path = self._get_file_path(item_index)
        files.append(file_path)
        self._file = open(file_path, "wb")

        for segment_index, segment in enumerate(self._m3u8_data.segments):
            if self._terminated:
                break

            ts_url = os.path.join(self._host_uri, segment.uri)  # Ссылка на сегмент
            logger.opt(colors=True).debug(
                f"Downloading segment <y>{segment.title}</y>({ts_url})"
            )

            # Определяем функцию дешифрования фрагмента
            decrypt_func = None
            if segment.key.method == "AES-128":
                if not key:
                    key_uri = segment.key.uri
                    key = urlopen(key_uri).read()

                ind = segment_index + self._m3u8_data.media_sequence
                iv = binascii.a2b_hex("%032x" % ind)
                cipher = AES.new(key, AES.MODE_CBC, iv=iv)
                decrypt_func = cipher.decrypt

            # Создаем объект потоковой загрузки фрагмента
            self._file_stream = requests.get(ts_url, timeout=10, stream=True)
            logger.opt(colors=True).debug(
                f"File size: <y>{self._file_stream.headers.get('content-length')}</y>"
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

            # Если длительность получившегося файла равна длительности главы
            # (погрешность 2 сек)
            if item.duration - get_audio_file_duration(file_path) < 2:
                self._file.close()
                self._file = None
                prepare_file_metadata(
                    file_path, self.book.author, item.title, item_index
                )
                # Переход к следующей главе
                if item_index + 1 < len(self.book.items):
                    item_index += 1
                    item = self.book.items[item_index]
                    file_path = self._get_file_path(item_index)
                    files.append(file_path)
                    self._file = open(file_path, "wb")

        return files

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
                f"{str(item_index + 1).rjust(2, '0')}. {item_title}.mp3",
            )
        )
        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        return file_path

from __future__ import annotations

import re
import typing as ty
from contextlib import suppress
from pathlib import Path

import requests
from loguru import logger

from ..base import BaseDownloader, DownloadProcessStatus
from ..tools import prepare_file_metadata


if ty.TYPE_CHECKING:
    from models.book import Book, BookItem
    from ..base import BaseDownloadProcessHandler


class MP3Downloader(BaseDownloader):
    """
    Загрузчик, предназначенный для книг в которых файлы представлены
    отдельными или объединенными MP3 файлами.
    """

    def __init__(
        self, book: Book, process_handler: BaseDownloadProcessHandler | None = None
    ):
        super().__init__(book, process_handler)

        self._files_urls = []  # Ссылки на файлы
        # True - в одном аудио файле присутствует не одна глава
        self.merged: bool = False

    def _prepare(self) -> None:
        if self.process_handler:
            self.total_size = 0
            # Инициализируем прогресс подготовки
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
                    # Определяем размер файла
                    file_stream = requests.get(url, stream=True)
                    self.total_size += int(
                        file_stream.headers.get("content-length") or 0
                    )
                    file_stream.close()
            else:
                self.merged = True

    def _download_book(self) -> list[Path]:
        if self.process_handler:
            # Инициализируем прогресс скачивания
            self.process_handler.init(
                self.total_size, status=DownloadProcessStatus.DOWNLOADING
            )

        files: list[Path] = []
        for i, item in enumerate(self.book.items):
            if self._terminated:
                break

            if self.merged:
                if item.file_url not in self._files_urls:
                    continue
                # Исключаем ссылку, чтобы не скачивать файл второй раз
                self._files_urls[item.file_index] = None

            file_path = self._get_file_path(item)
            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)
            self._download_file(file_path, item.file_url)
            files.append(file_path)

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

        return files

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

    def _download_file(self, file_path: Path, url: str) -> None:
        logger.opt(colors=True).debug(f"Download the file <y>{file_path}</y>({url})")

        self._file = open(file_path, "wb")
        self._file_stream = requests.get(url, timeout=10, stream=True)
        logger.opt(colors=True).debug(
            f"File size: <y>{self._file_stream.headers.get('content-length')}</y>"
        )
        with suppress(requests.exceptions.StreamConsumedError):
            for data in self._file_stream.iter_content(chunk_size=5120):
                if self._terminated:
                    break
                if self.process_handler:
                    self.process_handler.progress(len(data))
                self._file.write(data)
                self._file.flush()
            else:
                self._file_stream = None
                self._file.close()
                self._file = None

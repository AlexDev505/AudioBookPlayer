from __future__ import annotations

import typing as ty
from urllib.parse import urljoin

import aiohttp
from loguru import logger
from m3u8 import M3U8

from ..base import BaseDownloader, DownloadProcessStatus, File

if ty.TYPE_CHECKING:
    from models.book import Book, BookItem

    from ..base import BaseDownloadProcessHandler


class M3U8Downloader(BaseDownloader):
    """
    A loader designed for books in which files are presented M3U8 file.
    """

    def __init__(
        self,
        book: Book,
        process_handler: BaseDownloadProcessHandler | None = None,
    ):
        super().__init__(book, process_handler)

    def _prepare_files_data(self):
        pass

    async def _prepare_file_data(self, item_index: int, item: BookItem) -> None:
        async with aiohttp.ClientSession() as session:
            async with session.get(item.file_url) as response:
                m3u8_text = await response.text()
        m3u8_data = M3U8(m3u8_text, item.file_url.removesuffix("/play.m3u8"))
        url = urljoin(m3u8_data.base_uri, m3u8_data.segments[0].uri)
        duration = sum(segment.duration for segment in m3u8_data.segments)
        size = sum(map(int, m3u8_data.segments[-1].byterange.split("@"))) - int(
            m3u8_data.segments[0].byterange.split("@")[1]
        )
        ranges = [
            tuple(map(int, segment.byterange.split("@")))
            for segment in m3u8_data.segments
        ]
        ranges.insert(0, (ranges[0][1], 0))
        self.total_size += size
        self._files.append(
            File(
                index=item_index,
                name=self._get_item_file_name(item_index, ".m4a"),
                url=url,
                duration=duration,
                size=size,
                extra=dict(ranges=ranges),
            )
        )
        if self.process_handler:
            self.process_handler.progress(1)

    def _prepare(self):
        if self.process_handler:
            self.total_size = 0
            # Инициализируем прогресс подготовки
            self.process_handler.init(
                len(self.book.items), status=DownloadProcessStatus.PREPARING
            )

        self.tasks_manager.execute_tasks_factory(
            (
                self._prepare_file_data(i, item)
                for i, item in enumerate(self.book.items)
            )
        )
        self._files.sort(key=lambda x: x.index)

    async def _iter_chunks(self, file, offset=0):
        current_range_index = file.extra.get("current_range_index", 0)
        current_range = file.extra["ranges"][current_range_index]
        file.extra["headers"] = {
            "Range": f"bytes={max(offset, current_range[1])}-{sum(current_range) - 1}"
        }
        logger.trace(f"{file.extra['headers']}")
        async for chunk in super()._iter_chunks(file, 0):
            yield chunk
        if current_range_index + 1 == len(file.extra["ranges"]):
            return
        file.extra["current_range_index"] = current_range_index + 1
        async for chunk in self._iter_chunks(file, offset):
            yield chunk

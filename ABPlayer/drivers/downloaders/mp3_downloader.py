from __future__ import annotations

import typing as ty

from ..base import BaseDownloader


if ty.TYPE_CHECKING:
    pass


class MP3Downloader(BaseDownloader):
    """
    Загрузчик, предназначенный для книг в которых файлы представлены
    отдельными MP3 файлами.
    """

    def _prepare_files_data(self):
        return [
            (self._get_item_file_name(i), item.file_url)
            for i, item in enumerate(self.book.items)
        ]

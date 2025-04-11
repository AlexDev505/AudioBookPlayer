from __future__ import annotations

import typing as ty

from ..base import BaseDownloader


if ty.TYPE_CHECKING:
    pass


class MP3Downloader(BaseDownloader):
    """
    A loader designed for books in which files are presented
    separate mp3 files.
    """

    def _prepare_files_data(self):
        return [
            (self._get_item_file_name(i), item.file_url)
            for i, item in enumerate(self.book.items)
        ]

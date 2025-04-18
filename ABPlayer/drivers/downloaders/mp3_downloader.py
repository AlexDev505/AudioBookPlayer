from ..base import BaseDownloader, File


class MP3Downloader(BaseDownloader):
    """
    A loader designed for books in which files are presented
    separate mp3 files.
    """

    def _prepare_files_data(self):
        return [
            File(i, self._get_item_file_name(i), item.file_url)
            for i, item in enumerate(self.book.items)
        ]

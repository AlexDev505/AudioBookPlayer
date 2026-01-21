from ..base_downloader import BaseAudioDownloader, File


class MP3Downloader(BaseAudioDownloader):
    """
    A loader designed for books in which files are presented
    separate mp3 files.
    """

    def _prepare_files_data(self):
        return [
            File(i, self._get_chapter_file_name(i), item.url)
            for i, item in enumerate(self._book.source.chapters)
        ]

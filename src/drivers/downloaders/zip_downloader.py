import os
import zipfile

from ..base_downloader import BaseTextDownloader


class ZipDownloader(BaseTextDownloader):
    """
    A loader designed for books in which files are
    archived into a single zip file.
    """

    async def _file_downloaded(self, file, file_path) -> None:
        with zipfile.ZipFile(file_path) as zip_file:
            file_name = zip_file.namelist()[0]
            zip_file.extract(file_name, file_path.parent)
        os.remove(file_path)
        os.rename(file_path.parent / file_name, file_path.parent / file.name)

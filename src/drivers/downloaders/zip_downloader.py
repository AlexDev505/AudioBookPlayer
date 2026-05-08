import os
import zipfile
from pathlib import Path

from ..base_downloader import BaseTextDownloader


class ZipDownloader(BaseTextDownloader):
    """
    A loader designed for books in which files are
    archived into a single zip file.
    """

    async def _file_downloaded(self, file, file_path) -> None:
        with zipfile.ZipFile(file_path) as zip_file:
            file_name = Path(zip_file.namelist()[0])
            zip_file.extract(str(file_name), file_path.parent)
        os.remove(file_path)
        origin_fp = file_path.parent / (file.name + file_name.suffix)
        if os.path.exists(origin_fp):
            os.remove(origin_fp)
        os.rename(file_path.parent / file_name, origin_fp)
        self._downloaded_files[file.index] = origin_fp

import config  # noqa
from drivers.akniga import AKnigaDriver
from drivers.knigavuhe import KnigaVUhe
from drivers.base import DownloadProcessHandler
from database import Books
import os

drv = AKnigaDriver()

book = drv.get_book("https://akniga.org/bogomazov-sergey-revolyuciya")

drv.download_book(book, DownloadProcessHandler())
books = Books(os.environ["DB_PATH"])
books.insert(**vars(book))

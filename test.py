import config  # noqa
from drivers.akniga import AKnigaDriver
from drivers.knigavuhe import KnigaVUhe
from drivers.base import DownloadProcessHandler
from database import Books
import os

drv = KnigaVUhe()

book = drv.get_book("https://knigavuhe.org/book/podnjatie-urovnja-v-odinochku-20/")

drv.download_book(book, DownloadProcessHandler())
# books = Books(os.environ["DB_PATH"])
# books.insert(**vars(book))

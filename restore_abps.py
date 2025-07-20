"""

Script for restoring .abp files for books in DB.

"""

import os.path
import re

import config
import main  # noqa
from database import Database
from models.book import BookFiles
from tools import get_file_hash

config.init()

with Database() as db:
    books = db.get_libray(limit=10000)

    for book in books:
        if not os.path.exists(book.dir_path) or not book.files:
            continue
        book_files = BookFiles()
        for i, item in enumerate(book.items):
            item_title = re.sub(r"^(\d+) (.+)", r"\g<2>", item.title)
            file_name = f"{str(i + 1).rjust(2, '0')}. {item_title}.mp3"
            fp = os.path.join(book.dir_path, file_name)
            if not os.path.exists(fp):
                break
            book_files[file_name] = get_file_hash(fp)
        else:
            book.files = book_files
            db.save(book)
            db.commit()
            book.save_to_storage()

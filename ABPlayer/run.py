"""

Запуск приложения.

"""

import argparse
import sys
import time

from loguru import logger

import main

parser = argparse.ArgumentParser()
parser._print_message = lambda message, _: logger.debug(message)
parser.add_argument("--delete-later", action="store_true")
parser.add_argument("--download-book", type=str, default="")
args = parser.parse_args()

if args.delete_later:
    import delete_later

    time.sleep(2)
    delete_later.delete_paths()
    sys.exit()

if args.download_book:
    from ui_functions import book_series_page

    book_series_page.download_book(args.download_book)
    sys.exit()

main.main()

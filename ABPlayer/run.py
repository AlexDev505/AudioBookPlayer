"""

Запуск приложения.

"""

import argparse
import sys
import time

import main

parser = argparse.ArgumentParser()
parser.add_argument(
    "--delete-later",
    action="store_true",
)
args = parser.parse_args()

if args.delete_later:
    import delete_later

    time.sleep(2)
    delete_later.delete_files()
    sys.exit()

main.main()

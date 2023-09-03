"""

Запуск приложения.

"""

import argparse
import sys

from loguru import logger

import main


parser = argparse.ArgumentParser()
parser._print_message = lambda message, _: logger.debug(message)
parser.add_argument("--run-update", type=str, default="")
args = parser.parse_args()

if args.run_update:
    from ctypes import windll

    logger.info("Running updater")
    windll.shell32.ShellExecuteW(None, "runas", args.run_update, None, None, 1)
    sys.exit()

main.main()

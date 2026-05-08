"""

Running the application.

Startup parameters:
    --run-downloader runs downloader server
    --run-update runs update
    --only-stable if given updates to stable version
    --manual-update=<str> runs update from file

"""

import argparse
import os.path
import sys

from loguru import logger

import main

parser = argparse.ArgumentParser()
parser._print_message = lambda message, file=None: logger.debug(message)
parser.add_argument("--run-downloader", action="store_true", default=False)
args = parser.parse_args()

# if you run the application with a shortcut,
# the working directory will be "./_internal/yarl"
# moving to root dir necessary for correct work of updater
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

if args.run_downloader:
    import asyncio

    from drivers.downloader.downloader_server import run_server

    asyncio.run(run_server())
    sys.exit()

main.main()

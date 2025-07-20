"""

Running the application.

Startup parameters:
    --run-update runs update
    --only-stable if given updates to stable version
    --manual-update=<str> runs update from file

"""

import argparse
import os.path
import sys

import main
from loguru import logger

parser = argparse.ArgumentParser()
parser._print_message = lambda message, _: logger.debug(message)
parser.add_argument("--run-update", action="store_true", default=False)
parser.add_argument("--only-stable", action="store_true", default=False)
parser.add_argument("--manual-update", type=str, default="")
args = parser.parse_args()

# if you run the application with a shortcut,
# the working directory will be "./_internal/yarl"
# moving to root dir necessary for correct work of updater
if getattr(sys, "frozen", False):
    os.chdir(os.path.dirname(sys.executable))

if args.manual_update:
    from ctypes import windll

    logger.info("Running manual updater")
    windll.shell32.ShellExecuteW(
        None, "runas", args.manual_update, None, None, 1
    )
    sys.exit()
elif args.run_update:
    from ctypes import windll

    logger.info("Running updater")
    windll.shell32.ShellExecuteW(
        None,
        "runas",
        os.path.abspath(
            os.path.join(".", f"ABPlayerUpdater{os.environ['ARCH']}.exe")
        ),
        (
            f"--version={os.environ['VERSION']}"
            + (" --only-stable" if args.only_stable else "")
        ),
        None,
        1,
    )
    sys.exit()

main.main()

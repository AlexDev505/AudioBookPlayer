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

from loguru import logger

import main


parser = argparse.ArgumentParser()
parser._print_message = lambda message, _: logger.debug(message)
parser.add_argument("--run-update", action="store_true", default=False)
parser.add_argument("--only-stable", action="store_true", default=False)
parser.add_argument("--manual-update", type=str, default="")
args = parser.parse_args()

if args.manual_update:
    from ctypes import windll

    logger.info("Running manual updater")
    windll.shell32.ShellExecuteW(None, "runas", args.manual_update, None, None, 1)
    sys.exit()
elif args.run_update:
    from ctypes import windll

    logger.info("Running updater")
    root_dir = os.path.abspath(__file__).removesuffix(r"_internal\run.py")
    windll.shell32.ShellExecuteW(
        None,
        "runas",
        os.path.abspath(
            os.path.join(root_dir, f"ABPlayerUpdater{os.environ["ARCH"]}.exe")
        ),
        (
            f"--version={os.environ["VERSION"]}"
            + (" --only-stable" if args.only_stable else "")
        ),
        None,
        1,
    )
    sys.exit()

main.main()

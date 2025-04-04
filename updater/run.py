import argparse
import sys

from loguru import logger

import main


parser = argparse.ArgumentParser()
parser._print_message = lambda message, _: logger.debug(message)
parser.add_argument("--version", type=str, default=None)
parser.add_argument("--only-stable", action="store_true", default=False)
args = parser.parse_args()

if not args.version or args.only_stable is None:
    sys.exit()

main.main(args.version, args.only_stable)

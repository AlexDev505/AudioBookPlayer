"""

Запуск приложения.

"""

import sys
import traceback

import main
from tools import debug

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, tb):
    print("".join(traceback.format_exception(exctype, value, tb)))
    debug(traceback.format_exception(exctype, value, tb))
    sys._excepthook(exctype, value, tb)


sys.excepthook = exception_hook

main.main()

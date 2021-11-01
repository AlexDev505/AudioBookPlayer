import sys
import os
import main
import traceback

sys._excepthook = sys.excepthook


def exception_hook(exctype, value, t):
    print(exctype, value, t)
    with open(os.path.join(os.environ["APP_DIR"], "errors.log"), "a+") as file:
        file.writelines(["\n\n"] + traceback.format_exception(exctype, value, t))
    sys._excepthook(exctype, value, t)


sys.excepthook = exception_hook

main.main()

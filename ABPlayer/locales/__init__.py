import gettext
import os
import sys

if getattr(sys, "frozen", False):
    ROOT_DIR = getattr(sys, "_MEIPASS")
else:
    ROOT_DIR = "."


def set_language(lang: str) -> None:
    gettext.translation("base", os.path.join(ROOT_DIR, "locales"), [lang]).install()

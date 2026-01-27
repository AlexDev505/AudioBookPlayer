import gettext
import os
import sys

if getattr(sys, "frozen", False):
    LOCALES_DIR = os.path.join(getattr(sys, "_MEIPASS"), "locales")
else:
    LOCALES_DIR = os.path.dirname(__file__)


def set_language(lang: str) -> None:
    gettext.translation("base", LOCALES_DIR, [lang]).install()

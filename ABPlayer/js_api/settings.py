from __future__ import annotations

import os
import typing as ty
from pathlib import Path

from loguru import logger

from .js_api import JSApi


if ty.TYPE_CHECKING:
    pass


class SettingsApi(JSApi):
    @staticmethod
    def open_library_dir():
        logger.opt(colors=True).debug("request: <r>open library dir</r>")
        try:
            os.startfile(os.environ["books_folder"])
        except FileNotFoundError:
            Path(os.environ["books_folder"]).mkdir(parents=True, exist_ok=True)
            os.startfile(os.environ["books_folder"])

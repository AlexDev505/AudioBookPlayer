from __future__ import annotations

import os
import typing as ty
from pathlib import Path

from loguru import logger

import config
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

    def set_dark_mode(self, value: bool):
        config.update_config(dark_theme=str(int(value)))
        return self.make_answer()

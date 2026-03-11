import importlib
import os

from loguru import logger

import temp_file

from .js_api import JSApi


class WindowControlsApi(JSApi):
    def save_session(self) -> None:
        logger.debug("saving session data")
        data = {}
        if os.environ["PLATFORM"] == "Windows":
            window_controls = importlib.import_module(
                ".window_controls", package=__package__
            )
            scale_k = window_controls.query_scale_k()
            data["width"] = int(self._window.width / scale_k)
            data["height"] = int(self._window.height / scale_k)
        data["is_main_menu_opened"] = self._window.state.menu_opened
        # is_filter_menu_opened = self._window.evaluate_js("filter_menu_opened")
        # required_drivers = self._window.evaluate_js("required_drivers")
        data["volume"] = self._window.state.volume * 100
        data["speed"] = self._window.state.speed
        # last_listened_book_bid = self._window.evaluate_js(
        #     "(player.current_book)?player.current_book.bid:null"
        # )
        temp_file.update(**data)
        # if last_listened_book_bid is None:
        #     temp_file.delete_items("last_listened_book_bid")
        logger.trace("session data saved")

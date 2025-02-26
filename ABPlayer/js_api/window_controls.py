from __future__ import annotations

import time
import typing as ty
from ctypes import windll, Structure, c_long, byref

from loguru import logger

import temp_file
from .js_api import JSApi
from .tools import ttl_cache


if ty.TYPE_CHECKING:
    import webview


class WindowControlsApi(JSApi):
    def __init__(self):
        self._full_screen = False

    def close_app(self) -> None:
        logger.debug("closing app")
        self._save_session_at_exit()
        self._window.destroy()

    def minimize_app(self) -> None:
        logger.trace("minimizing window")
        self._window.minimize()

    def toggle_full_screen_app(self) -> None:
        self._window.toggle_fullscreen()
        self._full_screen = not self._full_screen
        logger.trace(f"full screen toggled: {self._full_screen}")

    def drag_window(self) -> None:
        if self._full_screen:
            self.toggle_full_screen_app()
            move_to_cursor(self._window)
        drag_window(self._window)

    def resize_drag(self, size_grip: str) -> None:
        resize_handler(self._window, size_grip)

    def _save_session_at_exit(self) -> None:
        logger.debug("saving session data")
        scale_k = query_scale_k()
        width = int(self._window.width / scale_k)
        height = int(self._window.height / scale_k)
        is_main_menu_opened = self._window.evaluate_js("menu_opened")
        is_filter_menu_opened = self._window.evaluate_js("filter_menu_opened")
        required_drivers = self._window.evaluate_js("required_drivers")
        volume = self._window.evaluate_js("player.volume") * 100
        speed = self._window.evaluate_js("player.speed")
        last_listened_book_bid = self._window.evaluate_js(
            "(player.current_book)?player.current_book.bid:null"
        )
        temp_file.update(
            width=width,
            height=height,
            is_main_menu_opened=is_main_menu_opened,
            is_filter_menu_opened=is_filter_menu_opened,
            required_drivers=",".join(required_drivers),
            volume=volume,
            speed=speed,
            **(
                dict(last_listened_book_bid=last_listened_book_bid)
                if last_listened_book_bid is not None
                else {}
            ),
        )
        if last_listened_book_bid is None:
            temp_file.delete_items("last_listened_book_bid")
        logger.trace("session data saved")


class POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]


def query_mouse_position() -> tuple[int, int]:
    pt = POINT()
    windll.user32.GetCursorPos(byref(pt))
    return pt.x, pt.y


def query_key_state(key_code) -> bool:
    return bool(windll.user32.GetKeyState(key_code) >> 15)


@ttl_cache(5)
def query_scale_k() -> float:
    """
    Screen scale (usually set to 125% on laptops)
    """
    return windll.shcore.GetScaleFactorForDevice(0) / 100


def resize(window: webview.Window, width: int, height: int) -> None:
    window.resize(width, height)


def move(window: webview.Window, x: int, y: int) -> None:
    scale_k = query_scale_k()
    window.move(int(x / scale_k), int(y / scale_k))


def resize_handler(window: webview.Window, size_grip):
    # Define initial cursor position, window, and its size
    start_x, start_y = query_mouse_position()
    start_win_x = window.x
    start_win_y = window.y
    start_width = window.width
    start_height = window.height

    scale_k = query_scale_k()

    logger.trace(f"resize started: {size_grip}")

    while True:
        # User released the mouse button
        if not query_key_state(0x01):
            logger.trace("resize finished")
            break

        current_x, current_y = query_mouse_position()

        # Define value changes depending on the capture area
        delta_width = delta_height = delta_x = delta_y = 0
        # Regular window resizing
        if "bottom" in size_grip:
            delta_height = current_y - start_y
        if "right" in size_grip:
            delta_width = current_x - start_x
        # Change window size position
        if "top" in size_grip:
            delta_y = current_y - start_y
            delta_height = -delta_y
            if (start_height + delta_height) / scale_k < window.min_size[1]:
                delta_height = int(window.min_size[1] * scale_k) - start_height
                delta_y = -delta_height
        if "left" in size_grip:
            delta_x = current_x - start_x
            delta_width = -delta_x
            if (start_width + delta_width) / scale_k < window.min_size[0]:
                delta_width = int(window.min_size[0] * scale_k) - start_width
                delta_x = -delta_width

        if delta_x or delta_y:
            # Change window position
            move(window, start_win_x + delta_x, start_win_y + delta_y)
        # Change window size
        resize(window, start_width + delta_width, start_height + delta_height)

        time.sleep(0.005)


def move_to_cursor(window: webview.Window) -> None:
    user32 = windll.user32
    screen_width = user32.GetSystemMetrics(0)
    mouse_x = query_mouse_position()[0]
    window_width = window.width
    window.move(int(mouse_x - (window_width * mouse_x / screen_width)), 0)


def drag_window(window: webview.Window) -> None:
    # Define initial cursor and window position
    start_x, start_y = query_mouse_position()
    start_win_x = window.x
    start_win_y = window.y

    logger.trace("drag started")

    while True:
        # User released the mouse button
        if not query_key_state(0x01):
            logger.trace("drag finished")
            break

        current_x, current_y = query_mouse_position()

        delta_x = current_x - start_x
        delta_y = current_y - start_y

        move(window, start_win_x + delta_x, start_win_y + delta_y)

        time.sleep(0.005)


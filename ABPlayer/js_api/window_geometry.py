from __future__ import annotations

import time
import typing as ty
from ctypes import windll, Structure, c_long, byref

from loguru import logger

from .tools import ttl_cache


if ty.TYPE_CHECKING:
    import webview


class POINT(Structure):
    _fields_ = [("x", c_long), ("y", c_long)]


def query_mouse_position() -> tuple[int, int]:
    pt = POINT()
    windll.user32.GetCursorPos(byref(pt))
    return pt.x, pt.y


@ttl_cache(5)
def query_scale_k() -> float:
    """
    Масштаб экрана(на ноутбуках обычно стоит 125%
    """
    return windll.shcore.GetScaleFactorForDevice(0) / 100


def resize(window: webview.Window, width: int, height: int) -> None:
    window.resize(width, height)


def move(window: webview.Window, x: int, y: int) -> None:
    scale_k = query_scale_k()
    window.move(int(x / scale_k), int(y / scale_k))


def resize_handler(window: webview.Window, size_grip):
    state_left = windll.user32.GetKeyState(0x01)

    # Определяем начальное положение курсора, окна и его размер
    start_x, start_y = query_mouse_position()
    start_win_x = window.x
    start_win_y = window.y
    start_width = window.width
    start_height = window.height

    scale_k = query_scale_k()

    logger.debug(f"Resize started: {size_grip}")

    while True:
        # Пользователь отпустил кнопку мыши
        if windll.user32.GetKeyState(0x01) != state_left:
            logger.debug("Resize finished")
            break

        current_x, current_y = query_mouse_position()

        # Определяем изменение значений в зависимости от области захвата
        delta_width = delta_height = delta_x = delta_y = 0
        # Обычное изменение размера окна
        if "bottom" in size_grip:
            delta_height = current_y - start_y
        if "right" in size_grip:
            delta_width = current_x - start_x
        # Изменение положения размера окна
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
            # Изменяем положение окна
            move(window, start_win_x + delta_x, start_win_y + delta_y)
        # Изменяем размер окна
        resize(window, start_width + delta_width, start_height + delta_height)

        time.sleep(0.005)


def move_to_cursor(window: webview.Window) -> None:
    user32 = windll.user32
    screen_width = user32.GetSystemMetrics(0)
    mouse_x = query_mouse_position()[0]
    window_width = window.width
    window.move(int(mouse_x - (window_width * mouse_x / screen_width)), 0)


def drag_window(window: webview.Window) -> None:
    state_left = windll.user32.GetKeyState(0x01)

    # Определяем начальное положение курсора и окна
    start_x, start_y = query_mouse_position()
    start_win_x = window.x
    start_win_y = window.y

    logger.debug(f"Drag started")

    while True:
        # Пользователь отпустил кнопку мыши
        if windll.user32.GetKeyState(0x01) != state_left:
            logger.debug("Drag finished")
            break

        current_x, current_y = query_mouse_position()

        delta_x = current_x - start_x
        delta_y = current_y - start_y

        move(window, start_win_x + delta_x, start_win_y + delta_y)

        time.sleep(0.005)

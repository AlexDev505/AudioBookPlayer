import webview
from loguru import logger

from .window_geometry import resize_handler, move_to_cursor, drag_window


class JSApi:
    def __init__(self):
        self._full_screen = False

    @property
    def _window(self) -> webview.Window:
        return webview.windows[0]

    def close_app(self) -> None:
        self._window.destroy()

    def minimize_app(self) -> None:
        self._window.minimize()

    def toggle_full_screen_app(self) -> None:
        self._window.toggle_fullscreen()
        self._full_screen = not self._full_screen

    def drag_window(self) -> None:
        if self._full_screen:
            self.toggle_full_screen_app()
            move_to_cursor(self._window)
        drag_window(self._window)

    def resize_drag(self, size_grip: str) -> None:
        resize_handler(self._window, size_grip)

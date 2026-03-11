import webview
from loguru import logger

from js_api import JSApi
from web.app import app

js_api = JSApi()


def _on_loaded(window: webview.Window):
    logger.info(f"loaded {window.get_current_url()}")


def _on_closing():
    logger.info("application closing")
    js_api.save_session()


def _on_closed():
    logger.info("application closed\n\n")


def _on_shown():
    logger.info("main window launched")


def _init_main_window(window: webview.Window):
    js_api.init(window)
    window.events.loaded += _on_loaded
    window.events.closing += _on_closing
    window.events.closed += _on_closed
    window.events.shown += _on_shown


def main_window() -> webview.Window:
    """
    Creates the main application window.
    :returns: An instance of the window.
    """

    logger.info("launching main window...")

    temp_data = {}
    assert (
        window := webview.create_window(
            "ABPLayer",
            app,
            width=temp_data.get("width", 1000),
            height=temp_data.get("height", 650),
            frameless=True,
            easy_drag=False,
            min_size=(920, 520),
            background_color="#202225",
        )
    )

    _init_main_window(window)

    return window


def main_window_on_place(window: webview.Window):
    logger.info("placing main window")

    window.events.loaded._items.clear()
    window.events.shown._items.clear()

    _init_main_window(window)

    window.load_url("/")

    logger.info("main window placed")

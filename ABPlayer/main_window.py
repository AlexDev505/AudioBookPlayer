import webview
from loguru import logger

import temp_file
from js_api import JSApi
from web.app import app


def main_window() -> webview.Window:
    """
    Creates the main application window.
    :returns: An instance of the window.
    """

    def _on_loaded():
        logger.debug(f"loaded {window.get_current_url()}")

    def _on_closed():
        logger.info("application closed\n\n")

    def _on_shown():
        logger.debug("main window launched")
        js_api.init(window)

    logger.info("launching main window...")

    js_api = JSApi()
    temp_data = temp_file.load()
    window = webview.create_window(
        "ABPLayer",
        app,
        width=temp_data.get("width", 1000),
        height=temp_data.get("height", 650),
        frameless=True,
        easy_drag=False,
        min_size=(920, 520),
        background_color="#202225",
        js_api=js_api,
    )

    # Adding event handlers
    window.events.loaded += _on_loaded
    window.events.closed += _on_closed
    window.events.shown += _on_shown

    return window

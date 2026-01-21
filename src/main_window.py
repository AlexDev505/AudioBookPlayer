import webview
from js_api import JSApi
from loguru import logger
from web.app import app

js_api = JSApi()

def _on_loaded(window: webview.Window):
    logger.info(f"loaded {window.get_current_url()}")

def _on_closed():
    logger.info("application closed\n\n")

def _on_shown(window: webview.Window):
    logger.info("main window launched")
    js_api.init(window)


def main_window() -> webview.Window:
    """
    Creates the main application window.
    :returns: An instance of the window.
    """

    logger.info("launching main window...")

    temp_data = {}
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


def main_window_on_place(window: webview.Window):
    logger.info("placing main window")

    window.events.loaded._items.clear()
    window.events.shown._items.clear()

    window.events.loaded += _on_loaded
    window.events.closed += _on_closed
    window.events.shown += _on_shown

    window.load_url("/")

    logger.info("main window placed")

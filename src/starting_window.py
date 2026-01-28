import os
import time

import webview
from loguru import logger

import config
import locales
from database import Database
from web.app import app


def _on_shown(window: webview.Window):
    logger.debug("starting window launched")
    window.load_url("/starting_window")


def _on_loaded(window: webview.Window):
    start_app(window)


def create_starting_window() -> webview.Window:
    """
    Creates the application startup window.
    :returns: An instance of the window.
    """

    logger.info("launching starting window...")

    window = webview.create_window(
        "ABPLayer",
        app,
        width=210,
        height=240,
        frameless=True,
        easy_drag=True,
        background_color="#202225",
    )

    # Adding event handlers
    window.events.loaded += _on_loaded
    window.events.shown += _on_shown

    return window


def start_app(window: webview.Window) -> None:
    """
    Prepares the application for launch.
    Initializes the configuration and database.
    Analyzes the library.
    """
    logger.debug("starting app...")
    start_time = time.time()

    updater_path = os.path.join(
        os.environ["APP_DIR"],
        f"ABPlayerSetup.{os.environ['VERSION']}"
        f"{os.environ['ARCH'].replace(' ', '.')}.{'exe' if os.environ['PLATFORM'] == 'Windows' else 'apk'}",
    )
    if os.path.isfile(updater_path):
        os.remove(updater_path)

    config.init()
    locales.set_language(os.environ["language"])
    Database.init(
        f"sqlite://{os.environ['DATABASE_PATH']}",
        check_same_thread=False,
    )

    window.run_js("setStatus('запуск...')")

    if (sub := time.time() - start_time) < 2:
        logger.trace(f"sleeping {round(2 - sub, 2)}s （*＾-＾*）")
        time.sleep(2 - sub)

    import main_window as main

    if os.environ["PLATFORM"] == "Windows":
        main.main_window()
        window.destroy()
    else:
        main.main_window_on_place(window)

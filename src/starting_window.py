import os
import time
import typing as ty

import webview
from loguru import logger

import config
import local_storage
import locales
from database import Database
from models.book import Book, SourceId, SourceType
from web.app import app


def _on_shown(window: webview.Window):
    logger.debug("starting window launched")
    window.load_url("/starting_window")


def _on_loaded(window: webview.Window):
    if not hasattr(window, "loaded"):
        setattr(window, "loaded", True)
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

    # Remove updater file if it exists
    updater_path = os.path.join(
        os.environ["APP_DIR"],
        f"ABPlayerSetup.{os.environ['VERSION']}"
        f"{os.environ['ARCH'].replace(' ', '.')}.{'exe' if os.environ['PLATFORM'] == 'Windows' else 'apk'}",
    )
    if os.path.isfile(updater_path):
        os.remove(updater_path)

    # Configuration initialization
    config.init()
    locales.set_language(os.environ["language"])

    # DB initialization
    Database.init(
        f"sqlite://{os.environ['DATABASE_PATH']}",
        check_same_thread=False,
    )
    Database().create_library()

    init_library(window)

    # Wait for... nothing)
    window.run_js("setStatus('запуск...')")
    if (sub := time.time() - start_time) < 2:
        logger.trace(f"sleeping {round(2 - sub, 2)}s （*＾-＾*）")
        time.sleep(2 - sub)

    import main_window as main

    if os.environ["PLATFORM"] == "Android":
        main.main_window_on_place(window)
    else:
        main.main_window()
        window.destroy()


def init_library(window: webview.Window) -> None:
    """
    Analyzes the library.
    Adds books from storage.
    Fixes incorrect entries in the database.
    """
    logger.debug("loading library...")
    window.evaluate_js("setStatus('загрузка библиотеки...')")

    db = Database()
    correct_source_urls: list[str] = []
    incorrect_sids: list[SourceId] = []

    # Checking existing books in the database
    logger.trace("validating exists books")
    offset = 0
    books = db.get_library(20, offset)
    while books:
        for book in books:
            for source in book.iter_sources():
                if source.is_downloaded:
                    if not local_storage.check_exists(book, source):
                        if source.url.startswith("file://"):
                            db.remove_source(SourceId.from_source(source))
                        else:
                            incorrect_sids.append(SourceId.from_source(source))
                    else:
                        correct_source_urls.append(source.url)
        offset += 20
        books = db.get_library(20, offset)

    if incorrect_sids:
        logger.debug(
            f"some sources have incorrect files data. sids: {incorrect_sids}"
        )
        db.clear_sources_files(incorrect_sids)

    # Scanning storage
    logger.trace("scanning books folder")
    for book, source in local_storage.scan(os.environ["books_folder"]):
        if source.url in correct_source_urls:
            logger.trace(f"{source.url} is correct")
            continue
        if db_source := db.get_source_by_url(
            SourceType(type(source)), source.url
        ):
            db_source.files = source.files
            db.save(db_source)
            logger.opt(colors=True).debug(
                f"files for <y>{source.url}</y> are restored"
            )
            continue
        if not (db_book := db.get_book_by_hash(book.hash)):
            db_book = ty.cast(Book, db.insert(book))
        source.related_book = db_book.id
        db.insert(source)

import os
import time
from functools import partial

import webview
from loguru import logger

import config
from database import Database
from models.book import Book
from tools import pretty_view
from web.app import app


def create_starting_window() -> webview.Window:
    def _on_shown():
        logger.debug("starting window launched")
        window.load_url("/starting_window")

    def _on_loaded():
        start_app(window)

    logger.info("launching starting window...")

    window = webview.create_window(
        "ABPLayer",
        app,
        width=210,
        height=240,
        frameless=True,
        easy_drag=True,
        background_color="#000",
    )

    # Добавляем обработчики событий
    window.events.loaded += _on_loaded
    window.events.shown += _on_shown

    return window


def start_app(window: webview.Window) -> None:
    logger.debug("starting app...")
    start_time = time.time()

    updater_path = os.path.join(
        os.environ["APP_DIR"], f"ABPlayerUpdate.{os.environ['VERSION']}.exe"
    )
    if os.path.isfile(updater_path):
        os.remove(updater_path)

    config.init()
    Database.init()
    init_library(window)

    window.evaluate_js("setStatus('запуск...')")

    if (sub := time.time() - start_time) < 2:
        logger.trace(f"sleeping {round(2 - sub, 2)}s （*＾-＾*）")
        time.sleep(2 - sub)

    import main_window as main

    main.main_window()
    window.destroy()


def init_library(window: webview.Window) -> None:
    logger.debug("loading library...")
    window.evaluate_js("setStatus('загрузка библиотеки...')")

    updates = False
    correct_books_urls: list[str] = []
    incorrect_books_ids: list[int] = []
    with Database() as db:
        logger.trace("validating exists books")
        offset = 0
        books = db.get_libray(20, offset)
        while books:
            for book in books:
                if book.files:
                    if not os.path.exists(book.dir_path):
                        incorrect_books_ids.append(book.id)
                    else:
                        correct_books_urls.append(book.url)
            offset += 20
            books = db.get_libray(20, offset)

        if incorrect_books_ids:
            logger.opt(lazy=True).debug(
                "some books have incorrect files data. bids: {data}",
                data=partial(pretty_view, incorrect_books_ids),
            )
            db.clear_files(*incorrect_books_ids)
            updates = True

        logger.trace("scanning books folder")
        for book in Book.scan_dir(os.environ["books_folder"]):
            if book.url in correct_books_urls:
                continue
            if db_book := db.get_book_by_url(book.url):
                if not db_book.files:
                    try:
                        os.remove(book.abp_file_path)
                    except IOError:
                        pass
                continue
            db.add_book(book)
            logger.opt(colors=True).debug(f"{book:styled} added to library")
            updates = True

        if updates:
            logger.trace("saving library")
            db.commit()

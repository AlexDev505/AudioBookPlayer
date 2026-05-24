import importlib
import os
import typing as ty
from pathlib import Path

import webview
from loguru import logger

import config
import local_storage
import locales
import temp_file
from database import Database
from js_api.exceptions import CanceledError
from models.book import Book, BookSource, SourceType

from .js_api import JSApi


class WindowControlsApi(JSApi):
    def __init__(self) -> None:
        self.old_books_folder: str | None = None

    @staticmethod
    def open_library_dir():
        logger.opt(colors=True).debug("request: <r>open library dir</r>")
        try:
            os.startfile(os.environ["books_folder"])
        except FileNotFoundError:
            Path(os.environ["books_folder"]).mkdir(parents=True, exist_ok=True)
            os.startfile(os.environ["books_folder"])

    def set_dark_mode(self, value: bool):
        logger.opt(colors=True).debug(
            f"request: <r>set dark mode</r> | <y>{value}</y>"
        )
        config.update_config(dark_theme=str(int(value)))

    def set_language(self, lang: str):
        logger.opt(colors=True).debug(
            f"request: <r>set language</r> | <y>{lang}</y>"
        )
        config.update_config(language=lang)
        locales.set_language(lang)

    def change_library_dir(self):
        if not (
            new_dir := self._window.create_file_dialog(
                dialog_type=webview.FileDialog.FOLDER,
                directory=os.environ["books_folder"],
            )
        ):
            logger.debug("dir not selected")
            raise CanceledError()

        new_dir = new_dir[0]
        self.old_books_folder = old_dir = os.environ["books_folder"]

        if new_dir == old_dir:
            logger.debug("selected same dir")
            raise CanceledError()

        config.update_config(books_folder=new_dir)
        logger.opt(colors=True).info(
            f"books folder changed: <e>{old_dir}</e> <g>-></g> <y>{new_dir}</y>"
        )

        db = Database()
        is_old_library_empty = not any(local_storage.scan(old_dir))
        db.clear_all_files()
        db.remove_self_loaded_sources()
        logger.debug("files data and self-loaded sources cleared from database")

        new_books_count = 0
        new_sources_count = 0
        for book, source in local_storage.scan(new_dir):
            if not (db_book := db.get_book_by_hash(book.hash)):
                db_book = ty.cast(Book, db.insert(book))
                new_books_count += 1
            if not (
                db_source := db.get_source_by_url(
                    SourceType(type(source)), source.url
                )
            ):
                source.related_book = db_book.id
                db.insert(source)
                new_sources_count += 1
            else:
                db_source.files = source.files
                db.save(db_source)

        logger.opt(colors=True).info(
            f"<y>{new_books_count}</y> new books and "
            f"<y>{new_sources_count}</y> new sources added to library"
        )

        return dict(
            is_old_library_empty=is_old_library_empty,
            new_books_count=new_books_count,
            new_sources_count=new_sources_count,
        )

    def migrate_old_library(self):
        if self.old_books_folder is None:
            raise CanceledError()

        moved_books_count = 0
        db = Database()
        for book, source in local_storage.scan(self.old_books_folder):
            if os.path.exists(book.dir_path / source.dir_path):
                logger.opt(colors=True).debug(
                    f"<y>{book.book_path / source.dir_path}</y> already exists"
                )
                continue
            db_source = db.get_source_by_url(
                SourceType(type(source)), source.url
            )
            if not db_source:
                if not source.url.startswith("file://"):
                    logger.opt(colors=True).debug(
                        f"{source:colored} not found in library"
                    )
                    continue
                db_book = ty.cast(Book, db.get_book_by_hash(book.hash))
                source.related_book = db_book.id
                db_source = ty.cast(BookSource, db.insert(source))

            old_dir_path = Path(
                self.old_books_folder, book.book_path, source.dir_path
            )
            (new_dir_path := book.dir_path / source.dir_path).mkdir(
                parents=True, exist_ok=True
            )
            logger.opt(colors=True).debug(
                f"moving {source:colored} "
                f"<e>{old_dir_path}</e> <g>-></g> <y>{new_dir_path}</y>"
            )

            if not local_storage.move(
                old_dir_path, new_dir_path, list(source.files)
            ):
                continue

            db_source.files = source.files
            db.save(db_source)

            moved_books_count += 1
            logger.opt(colors=True).debug(f"{source:colored} moved")

        logger.opt(colors=True).debug(
            f"books moved: <y>{moved_books_count}</y>"
        )

        return dict(moved_books_count=moved_books_count)

    def remove_old_library(self):
        if self.old_books_folder is None:
            raise CanceledError()

        removed_books_count = 0
        db = Database()
        for book, _ in local_storage.scan(self.old_books_folder):
            if os.path.exists(book.dir_path):
                logger.opt(colors=True).debug(
                    f"{book:colored} exists in new library"
                )
                continue
            if not (db_book := db.get_book_by_hash(book.hash)):
                continue

            db.remove_book(db_book.id)
            removed_books_count += 1
            logger.opt(colors=True).debug(
                f"{book:colored} and sources are removed"
            )

        logger.opt(colors=True).debug(
            f"books removed: <y>{removed_books_count}</y>"
        )

        return dict(removed_books_count=removed_books_count)

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

from __future__ import annotations

import os
import shutil
import typing as ty
from pathlib import Path

import webview
from loguru import logger

import config
from database import Database
from models.book import Book
from .js_api import JSApi, JSApiError


if ty.TYPE_CHECKING:
    pass


class SettingsApi(JSApi):
    def __init__(self):
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
        logger.opt(colors=True).debug(f"request: <r>set dark mode</r> | <y>{value}</y>")
        config.update_config(dark_theme=str(int(value)))
        return self.make_answer()

    def change_library_dir(self):
        logger.opt(colors=True).debug("request: <r>change library dir</r>")
        if not (
            new_dir := self._window.create_file_dialog(
                dialog_type=webview.FOLDER_DIALOG,
                directory=os.environ["books_folder"],
            )
        ):
            logger.debug("dir not selected")
            return self.error(RequestCanceled())

        new_dir = new_dir[0]
        self.old_books_folder = old_dir = os.environ["books_folder"]

        if new_dir == old_dir:
            logger.debug("selected same dir")
            return self.error(RequestCanceled())

        config.update_config(books_folder=new_dir)
        logger.opt(colors=True).info(
            f"books folder changed: <e>{old_dir}</e> <g>-></g> <y>{new_dir}</y>"
        )

        books = Book.scan_dir(new_dir)
        with Database() as db:
            db.clear_files()
            logger.debug("files data cleared from database")
            is_old_library_empty = db.is_library_empty()

            exists_books_urls = db.check_is_books_exists([book.url for book in books])
            new_books_count = 0
            for book in books:
                if book.url in exists_books_urls:
                    continue
                new_books_count += 1
                db.add_book(book)

            if new_books_count:
                db.commit()

            logger.opt(colors=True).debug(
                f"<y>{new_books_count}</y> new books added to library"
            )

        return self.make_answer(
            dict(
                is_old_library_empty=is_old_library_empty,
                new_books_count=new_books_count,
            )
        )

    def migrate_old_library(self):
        logger.opt(colors=True).debug("request: <r>migrate old library</r>")
        if self.old_books_folder is None:
            return self.error(RequestCanceled())

        books = Book.scan_dir(self.old_books_folder)
        moved_books_count = 0
        with Database() as db:
            for book in books:
                if os.path.exists(book.dir_path):
                    logger.opt(colors=True).debug(f"{book:styled} already exists")
                    continue
                db_book = db.get_book_by_url(book.url)
                if not db_book:
                    logger.opt(colors=True).debug(f"{book:styled} not found in library")
                    continue

                old_dir_path = os.path.join(self.old_books_folder, book.book_path)
                Path(new_dir_path := book.dir_path).mkdir(parents=True, exist_ok=True)
                logger.opt(colors=True).debug(
                    f"moving {book:styled} "
                    f"<e>{old_dir_path}</e> <g>-></g> <y>{new_dir_path}</y>"
                )
                for file_name in [*book.files, ".abp", "cover.jpg"]:
                    try:
                        shutil.move(
                            os.path.join(old_dir_path, file_name),
                            os.path.join(new_dir_path, file_name),
                        )
                        logger.opt(colors=True).trace(f"file <y>{file_name}</y> moved")
                    except IOError as err:
                        logger.error(
                            f"failed on moving {file_name}. {type(err).__name__}: {err}"
                        )
                try:
                    os.removedirs(old_dir_path)
                except IOError:
                    pass

                db_book.files = book.files
                db.save(db_book)

                moved_books_count += 1
                logger.opt(colors=True).debug(f"{book:styled} moved")

            if moved_books_count:
                db.commit()

        logger.opt(colors=True).debug(f"books moved: <y>{moved_books_count}</y>")

        return self.make_answer(dict(moved_books_count=moved_books_count))

    def remove_old_library(self):
        logger.opt(colors=True).debug("request: <r>remove old library</r>")
        if self.old_books_folder is None:
            return self.error(RequestCanceled())

        books = Book.scan_dir(self.old_books_folder)
        removed_books_count = 0
        with Database() as db:
            for book in books:
                if os.path.exists(book.dir_path):
                    logger.opt(colors=True).debug(
                        f"{book:styled} exists in new library"
                    )
                    continue
                if not (db_book := db.get_book_by_url(book.url)):
                    continue

                db.remove_book(db_book.id)
                removed_books_count += 1
                logger.opt(colors=True).debug(f"{book:styled} removed")

            if removed_books_count:
                db.commit()

        logger.opt(colors=True).debug(f"books removed: <y>{removed_books_count}</y>")

        return self.make_answer(dict(removed_books_count=removed_books_count))


class RequestCanceled(JSApiError):
    code = 7
    message = "Операция отменена"

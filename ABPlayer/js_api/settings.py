from __future__ import annotations

import os
import re
import shutil
import sys
import time
import typing as ty
from pathlib import Path
from subprocess import Popen

import requests
import webview
from loguru import logger
from orjson import orjson

import config
import locales
import temp_file
from database import Database
from models.book import Book
from .js_api import JSApi, JSApiError, ConnectionFailedError


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

    def set_language(self, lang: str):
        logger.opt(colors=True).debug(f"request: <r>set language</r> | <y>{lang}</y>")
        config.update_config(language=lang)
        locales.set_language(lang)
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

        books = list(Book.scan_dir(new_dir))
        with Database() as db:
            db.clear_files()
            logger.debug("files data cleared from database")
            is_old_library_empty = db.is_library_empty()

            exists_books_urls = db.check_is_books_exists([book.url for book in books])
            new_books_count = 0
            for book in books:
                if book.url in exists_books_urls:
                    db_book = db.get_book_by_url(book.url)
                    db_book.files = book.files
                    db.save(db_book)
                    continue
                new_books_count += 1
                db.add_book(book)

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

        moved_books_count = 0
        with Database() as db:
            for book in Book.scan_dir(self.old_books_folder):
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

        removed_books_count = 0
        with Database() as db:
            for book in Book.scan_dir(self.old_books_folder):
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

    def check_for_updates(self):
        logger.opt(colors=True).debug("request: <r>check for updates</r>")

        if isinstance(last_release := self._get_last_release(), JSApiError):
            return self.error(last_release)

        last_version = last_release["tag_name"]
        if last_version == os.environ["VERSION"]:
            logger.debug("The same version is installed now")
            return self.make_answer(False)

        stable = re.fullmatch(r"\d+\.\d+\.\d+", last_version) is not None

        return self.make_answer(
            dict(version=last_version, stable=stable, url=last_release["html_url"])
        )

    @staticmethod
    def _get_last_release() -> dict | JSApiError:
        logger.debug("Getting last release")
        try:
            response = requests.get(
                "https://api.github.com/repos/AlexDev505/AudioBookPlayer/releases"
            )
            if response.status_code != 200:
                raise requests.RequestException(
                    f"Response status code: {response.status_code}"
                )
        except requests.exceptions.RequestException as err:
            return ConnectionFailedError(err=f"{type(err).__name__}: {err}")

        releases = orjson.loads(response.text)
        last_release = releases[0]
        logger.opt(colors=True).debug(
            f"Last release: <y>{last_release['html_url']}</y>"
        )
        return last_release

    def update_app(self):
        logger.opt(colors=True).debug("request: <r>update appy</r>")

        if isinstance(last_release := self._get_last_release(), JSApiError):
            return self.error(last_release)

        last_version = last_release["tag_name"]
        updater_file_name = f"ABPlayerUpdate.{last_version}.exe"
        for asset in last_release["assets"]:
            if updater_file_name == asset["name"]:
                updater_url = asset["browser_download_url"]
                break
        else:
            logger.opt(colors=True).error(
                f"file <y>{updater_file_name}</y> not found in release assets"
            )
            return self.error(UpdateFileNotFound())

        updater_path = os.path.join(os.environ["APP_DIR"], updater_file_name)
        logger.opt(colors=True).debug(
            f"downloading updater file. <y>url={updater_url} path={updater_path}</y>"
        )
        if not self._download_updater(updater_url, updater_path):
            return self.error(ConnectionFailedError())

        logger.info("closing app")
        self._window.destroy()
        Popen([sys.executable, f"--run-update={updater_path}"])

    def unsubscribe_not_stable(self):
        temp_file.update(only_stable=True)
        logger.debug("unsubscribed from not stable releases")
        return self.make_answer()

    def _download_updater(
        self, updater_url: str, updater_path: str, _retries: int = 0
    ) -> bool:
        try:
            response = requests.get(updater_url)
            if response.status_code != 200:
                logger.error(
                    "updater downloading failed. "
                    f"Response status code {response.status_code}"
                )
                return False
            with open(updater_path, "wb") as file:
                file.write(response.content)
            return True
        except IOError as err:
            logger.error(
                f"Updater downloading failed on {_retries} retry. "
                f"{type(err).__name__}: {err}"
            )
            if _retries == 3:
                return False
            time.sleep(10 * _retries)
            return self._download_updater(updater_url, updater_path, _retries + 1)


class RequestCanceled(JSApiError):
    code = 7
    message = _("canceled")


class UpdateFileNotFound(JSApiError):
    code = 8
    message = _("update.file_not_found")

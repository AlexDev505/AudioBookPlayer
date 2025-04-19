from __future__ import annotations

import os
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
from tools import Version
from .js_api import JSApi, JSApiError, ConnectionFailedError


if ty.TYPE_CHECKING:
    pass


RELEASE_PAGE_URL = "https://github.com/AlexDev505/AudioBookPlayer/releases/tag/{tag}"
UPDATER_FILE_URL = (
    f"https://sourceforge.net/projects/audiobookplayer/files/"
    f"ABPlayerUpdater{os.environ["ARCH"]}.exe/download"
)


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

        if os.environ.get("DEBUG"):  # do not update the DEV build
            return self.make_answer(False)

        if isinstance(updates := self._get_updates(), JSApiError):
            return self.error(updates)

        if list(updates.keys())[0] == os.environ["VERSION"]:
            logger.debug("The same version is installed now")
            return self.make_answer(False)

        versions = list(updates.keys())
        last_stable_version = next(
            version for version in versions if Version.from_str(version).is_stable
        )
        if os.environ["VERSION"] not in versions:
            return self.make_answer(
                dict(
                    version=last_stable_version,
                    stable=True,
                    manual=True,
                    url=RELEASE_PAGE_URL.format(tag=last_stable_version),
                )
            )

        temp_data = temp_file.load()
        all_new_versions = versions[: versions.index(os.environ["VERSION"])]
        new_versions = [
            version
            for version_str in all_new_versions
            if (version := Version.from_str(version_str)).is_stable
        ]  # only stable releases
        if (
            not temp_data.get("only_stable", False)
            and not (version := Version.from_str(all_new_versions[0])).is_stable
        ):
            # if not only_stable and latest release is not stable,
            # add it to new releases
            new_versions.insert(0, version)
        if not new_versions:
            return self.make_answer(False)
        if any(updates[str(version)].get("manual") for version in new_versions):
            return self.make_answer(
                dict(
                    version=last_stable_version,
                    stable=True,
                    manual=True,
                    url=RELEASE_PAGE_URL.format(tag=last_stable_version),
                )
            )
        return self.make_answer(
            dict(
                version=str(new_versions[0]),
                stable=new_versions[0].is_stable,
                url=RELEASE_PAGE_URL.format(tag=str(new_versions[0])),
            )
        )

    def update_app(self, version: str | None = None):
        if version:
            return self._manual_update(version)

        logger.opt(colors=True).debug("request: <r>update app</r>")

        if isinstance(updates := self._get_updates(), JSApiError):
            return self.error(updates)

        updater_file_name = f"ABPlayerUpdater{os.environ["ARCH"]}.exe"
        root_dir = os.path.abspath(__file__).split(r"\_internal")[0]
        updater_path = os.path.abspath(os.path.join(root_dir, updater_file_name))

        versions = list(updates.keys())
        new_versions = versions[: versions.index(os.environ["VERSION"])]
        if next(
            (True for version in new_versions if updates[version].get("updater")),
            False,
        ):
            logger.debug("needs new updater")
            logger.opt(colors=True).debug(
                "downloading updater file. "
                f"<y>url={UPDATER_FILE_URL} path={updater_path}</y>"
            )
            if not self._download_updater(UPDATER_FILE_URL, updater_path):
                return self.error(ConnectionFailedError())

        logger.info("closing app")
        self._window.destroy()
        cmd = [sys.executable, "--run-update"]
        temp_data = temp_file.load()
        if temp_data.get("only_stable", False):
            cmd.append("--only-stable")
        Popen(cmd)

    def _manual_update(self, version: str):
        logger.opt(colors=True).debug(f"request: <r>manual update app to {version}</r>")

        if isinstance(release := self._get_release(version), JSApiError):
            return self.error(release)

        updater_file_name = (
            f"ABPlayerSetup.{version}{os.environ["ARCH"].replace(" ", ".")}.exe"
        )
        for asset in release["assets"]:
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
        Popen([sys.executable, f"--manual-update={updater_path}"])

    def unsubscribe_not_stable(self):
        temp_file.update(only_stable=True)
        logger.debug("unsubscribed from not stable releases")
        return self.make_answer()

    @staticmethod
    def _request(url: str) -> dict | JSApiError:
        try:
            response = requests.get(url)
            if response.status_code != 200:
                raise requests.RequestException(
                    f"Response status code: {response.status_code}"
                )
        except requests.exceptions.RequestException as err:
            return ConnectionFailedError(err=f"{type(err).__name__}: {err}")

        return orjson.loads(response.text)

    def _get_updates(self) -> dict | JSApiError:
        logger.debug("Getting updates")
        return self._request(
            "https://sourceforge.net/projects/audiobookplayer/files/"
            "updates.json/download"
        )

    def _get_release(self, version: str) -> dict | JSApiError:
        logger.debug(f"getting release {version}")
        return self._request(
            "https://api.github.com/repos/AlexDev505/AudioBookPlayer/releases/tags/"
            f"{version}"
        )

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

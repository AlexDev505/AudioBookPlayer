import asyncio
import hashlib
import json
import os
import shutil
import sys
import time
import typing as ty
import urllib.request
from pathlib import Path

import aiohttp
import requests
import webview
from io_tasks import IOTasksManager
from loguru import logger
from version import Version
from web.app import app


def create_updating_window() -> webview.Window:
    """
    Creates an application update window.
    :returns: window copy.
    """

    def _on_shown():
        logger.debug("updating window launched")
        window.load_url("/")

    def _on_loaded():
        try:
            update_app(window)
        except Exception as e:
            logger.exception(e)
        from ctypes import windll

        windll.shell32.ShellExecuteW(
            None, "open", os.path.abspath("./abplayer.exe"), None, None, 1
        )
        window.destroy()

    logger.info("launching updating window...")

    window = webview.create_window(
        "ABPLayer",
        app,
        width=210,
        height=240,
        frameless=True,
        easy_drag=True,
        background_color="#000000",
    )

    # Add events handlers
    window.events.loaded += _on_loaded
    window.events.shown += _on_shown

    return window


def update_app(window) -> None:
    logger.debug("updating app...")

    window.evaluate_js("setStatus('поиск обновлений...')")

    current_updater_version = Version.from_str(os.environ["UPDATER_VERSION"])
    arch = "x64" if not os.environ["ARCH"] else "x32"
    resp = urllib.request.urlopen(
        "https://sourceforge.net/projects/audiobookplayer/files/updates.json/download"
    )
    # all updates
    updates: dict[str, dict[str, ...]] = json.loads(resp.read().decode("utf-8"))
    versions = list(
        updates.keys()
    )  # all versions. versions[0] - latest version
    all_new_versions = versions[: versions.index(os.environ["VERSION"])]
    new_versions = [
        version
        for version_str in all_new_versions
        if (version := Version.from_str(version_str)).is_stable
    ]  # only stable releases
    if (
        not os.environ.get("ONLY_STABLE", False)
        and not (version := Version.from_str(all_new_versions[0])).is_stable
    ):  # if not ONLY_STABLE and latest release is not stable, add it to new releases
        new_versions.insert(0, version)
    if not new_versions:
        logger.info("no new versions available")
        window.evaluate_js("setStatus('нет обновлений')")
        return
    if any(updates[str(version)].get("manual") for version in new_versions):
        logger.info("needs manual update")
        window.evaluate_js("setStatus('требуется ручное обновление')")
        return
    if any(
        Version.from_str(upd_version) > current_updater_version
        for version in new_versions
        if (upd_version := updates[str(version)].get("updater"))
    ):
        logger.info("needs new updater")
        window.evaluate_js("setStatus('требуется новый апдейтер')")
        return

    logger.opt(colors=True).debug(
        f"new versions: {', '.join(map(lambda x: f'<y>{x}</y>', new_versions))}"
    )
    window.evaluate_js("setStatus('получение информации')")
    files_to_remove: list[str] = []
    files_to_update: dict[str, Version] = {}
    for version in new_versions[::-1]:
        resp = urllib.request.urlopen(
            f"https://sourceforge.net/projects/audiobookplayer/files/{version}/{arch}"
            "/update.json/download"
        )  # getting full info about release
        update = json.loads(resp.read().decode("utf-8"))
        files_to_remove.extend(update["update"]["remove"])
        files_to_update.update(
            {file: version for file in update["update"]["new"]}
        )

    update_path = Path(os.path.join(os.environ["APP_DIR"], "update"))
    update_path.mkdir(exist_ok=True)
    hashes = {}
    logger.info("downloading updates")
    files_count = len(files_to_update)
    window.evaluate_js(f"initDownloading({files_count})")
    tasks_manager = IOTasksManager(3)
    tasks_manager.execute_tasks_factory(
        (
            _download_file(file, version, arch, update_path, hashes, window)
            for file, version in files_to_update.items()
        )
    )

    logger.info("installing updates")
    window.evaluate_js("setStatus('установка')")
    window.evaluate_js("finishDownloading()")

    for file in files_to_remove:
        path = "\\".join(file.split("\\")[1:])
        if os.path.exists(path):
            os.remove(path)

    for file, file_hash in hashes.items():  # installing files
        dst_path = Path(*file.split("\\")[1:])
        if not os.path.exists(dst_path.parent):
            dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(os.path.join(update_path, file_hash), dst_path)


async def _download_file(
    file: str,
    version: Version,
    arch: str,
    update_path: Path,
    hashes: dict[str, str],
    window: webview.Window,
) -> None:
    fp = f"{version}/{arch}/{file.replace('\\', '/')}"
    url = (
        f"https://sourceforge.net/projects/audiobookplayer/files/{fp}/download"
    )
    logger.debug(f"downloading {fp}")
    file_name = hashlib.md5(file.encode("utf-8")).hexdigest()
    hashes[file] = file_name
    with open(os.path.join(update_path, file_name), "wb") as f:
        await __download_file(url, f, window)


async def __download_file(
    url: str,
    file: ty.BinaryIO,
    window: webview.Window,
    offset: int = 0,
    _retry: int = 0,
) -> None:
    if not (session := getattr(__download_file, "session", None)):
        session = aiohttp.ClientSession()
        setattr(__download_file, "session", session)
    try:
        async with session.get(
            url, headers={"Range": f"bytes={offset}-"}
        ) as resp:
            if resp.headers.get("content-type") != "application/octet-stream":
                await asyncio.sleep(5)
                raise RuntimeError("Invalid content type")
            total_size = int(resp.headers.get("content-length", 1))
            async for chunk in resp.content.iter_chunked(5120):
                offset += len(chunk)
                file.write(chunk)
                window.evaluate_js(
                    f"downloadingCallback({offset / (total_size / 100)})"
                )
    except (requests.exceptions.ConnectionError, RuntimeError):
        if _retry == 3:
            logger.error(f"Failed to download file: {url}")
            window.evaluate_js("setStatus('ошибка. повторите позже')")
            window.evaluate_js("finishDownloading()")
            time.sleep(5)

            from ctypes import windll

            windll.shell32.ShellExecuteW(
                None, "open", os.path.abspath("./abplayer.exe"), None, None, 1
            )
            window.destroy()
            sys.exit()
        return await __download_file(url, file, window, offset, _retry + 1)

    window.evaluate_js("fileDownloaded()")

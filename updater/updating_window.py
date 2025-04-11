import hashlib
import json
import os
import shutil
import urllib.request
from pathlib import Path

import webview
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

    window.evaluate_js("setStatus('проверка наличия обновлений...')")

    updater_version = Version.from_str(os.environ["UPDATER_VERSION"])
    arch = "x64" if not os.environ["ARCH"] else "x32"
    resp = urllib.request.urlopen(
        "https://sourceforge.net/projects/audiobookplayer/files/updates.json/download"
    )
    updates: dict[str, dict[str, ...]] = json.loads(resp.read().decode("utf-8"))
    versions = list(updates.keys())
    new_versions = versions[: versions.index(os.environ["VERSION"])]
    if any(updates[version].get("manual") for version in new_versions):
        logger.debug("needs manual update")
        window.evaluate_js("setStatus('требуется ручное обновление')")
        return
    if any(
        Version.from_str(upd_version) > updater_version
        for version in new_versions
        if (upd_version := updates[version].get("updater"))
    ):
        logger.debug("needs new updater")
        window.evaluate_js("setStatus('требуется новый апдейтер')")
        return
    new_versions = [
        version
        for version_str in new_versions
        if (version := Version.from_str(version_str)).is_stable
        or not os.environ.get("ONLY_STABLE", False)
    ]
    if not new_versions:
        logger.info("no new versions available")
        window.evaluate_js("setStatus('нет обновлений')")
        return

    logger.opt(colors=True).info(
        f"new versions: {", ".join(map(lambda x: f"<y>{x}</y>", new_versions))}"
    )
    window.evaluate_js("setStatus('получение информации')")
    files_to_remove: list[str] = []
    files_to_update: dict[str, Version] = {}
    for version in new_versions[::-1]:
        resp = urllib.request.urlopen(
            f"https://sourceforge.net/projects/audiobookplayer/files/{version}/{arch}"
            "/update.json/download"
        )
        update = json.loads(resp.read().decode("utf-8"))
        files_to_remove.extend(update["update"]["remove"])
        files_to_update.update({file: version for file in update["update"]["new"]})

    update_path = Path(os.path.join(os.environ["APP_DIR"], "update"))
    update_path.mkdir(exist_ok=True)
    hashes = {}
    logger.info("downloading updates")
    files_count = len(files_to_update)
    downloaded = 0
    window.evaluate_js(f"initProgresBar({files_count})")
    for file, version in files_to_update.items():
        fp = f"{version}/{arch}/{file.replace("\\", "/")}"
        logger.debug(f"downloading {fp}")
        resp = urllib.request.urlopen(
            f"https://sourceforge.net/projects/audiobookplayer/files/{fp}/download"
        )
        file_name = hashlib.md5(file.encode("utf-8")).hexdigest()
        hashes[file] = file_name
        with open(os.path.join(update_path, file_name), "wb") as f:
            f.write(resp.read())
        downloaded += 1
        window.evaluate_js(
            f"downloadingCallback({downloaded / (files_count / 100)}, {downloaded})"
        )

    logger.info("installing updates")
    window.evaluate_js("setStatus('установка')")
    window.evaluate_js("finishDownloading()")

    for file in files_to_remove:
        path = "\\".join(file.split("\\")[1:])
        if os.path.exists(path):
            os.remove(path)

    for file, file_hash in hashes.items():
        dst_path = Path(*file.split("\\")[1:])
        if not os.path.exists(dst_path.parent):
            dst_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(os.path.join(update_path, file_hash), dst_path)

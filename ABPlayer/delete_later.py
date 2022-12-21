from __future__ import annotations

import os
import pathlib
import subprocess
import sys
from contextlib import suppress

from loguru import logger

import temp_file


def add_file(file_path: str) -> None:
    data = temp_file.load()
    if "delete_later" not in data:
        data["delete_later"] = ""
    data["delete_later"] += file_path + ";"
    temp_file.dump(data)


def get_files_count() -> int:
    data = temp_file.load()
    return len((data.get("delete_later") or "").split(";"))


@logger.catch
def delete_files() -> None:
    data = temp_file.load()
    for file_path in (data.get("delete_later") or "").split(";"):
        try:
            file_path = pathlib.Path(file_path)
            if file_path.exists():
                os.remove(file_path)
                if file_path.is_file():
                    with suppress(Exception):
                        os.rmdir(file_path.parent)
        except Exception as err:
            logger.opt(colors=True).error(
                f"Can't delete file <y>{file_path}</y>. err: {err}"
            )
    temp_file.delete_items("delete_later")


def start_subprocess() -> None:
    subprocess.Popen([sys.executable, *sys.argv, "--delete-later"])

"""

    Модуль для работы с элементами, которые не удалось удалить сразу.

"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

from loguru import logger

import temp_file


def add_path(path: str) -> None:
    """
    Добавляет файл в список на удаление.
    :param path: Путь к файлу.
    """
    data = temp_file.load()
    if "delete_later" not in data:
        data["delete_later"] = ""
    data["delete_later"] += path + ";"
    temp_file.dump(data)


def get_paths_count() -> int:
    """
    :return: Кол-во элементов, которые нужно удалить.
    """
    data = temp_file.load()
    return len((data.get("delete_later") or "").split(";"))


@logger.catch
def delete_paths() -> None:
    """
    Удаляет элементы.
    """
    data = temp_file.load()
    for path in (data.get("delete_later") or "").split(";"):
        try:
            path = pathlib.Path(path)
            if path.exists():
                if path.is_file():
                    os.remove(path)
                elif path.is_dir():
                    os.rmdir(path)
        except Exception as err:
            logger.opt(colors=True).error(f"Can't delete <y>{path}</y>. err: {err}")
    temp_file.delete_items("delete_later")


def start_subprocess() -> None:
    """
    Запускает удаления файлов в другом процессе.
    """
    subprocess.Popen(
        [
            sys.executable,
            *(sys.argv[1:] if sys.argv[0] == sys.executable else sys.argv),
            "--delete-later",
        ]
    )

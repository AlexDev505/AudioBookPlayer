from __future__ import annotations

import json
import os
import re
import subprocess
import typing as ty

import eyed3


if ty.TYPE_CHECKING:
    from pathlib import Path


class NotImplementedVariable:
    def __get__(self, instance, owner):
        raise NotImplementedError()


def prepare_file_metadata(
    file_path: ty.Union[str, Path],
    author: str,
    title: str,
    item_index: int,
) -> None:
    """
    Изменяет метаданные аудио файла.
    :param file_path: Путь к аудио файлу.
    :param author: Автор книги.
    :param title: Название главы.
    :param item_index: Порядковый номер файла.
    """
    file = eyed3.load(file_path)
    file.initTag()
    file.tag.title = title
    file.tag.artist = author
    file.tag.track_num = item_index + 1
    file.tag.save()


def get_audio_file_duration(file_path: Path) -> float:
    result = subprocess.check_output(
        rf'{os.environ["FFPROBE_PATH"]} -v quiet -show_streams -of json "{file_path}"',
        shell=True,
    ).decode()
    fields = json.loads(result)["streams"][0]
    return float(fields["duration"])


def safe_name(text: str) -> str:
    while text.count('"') >= 2:
        text = re.sub(r'"(.*?)"', r"«\g<1>»", text)
    return re.sub(r'[\\/:*?"<>|+]', "", text)


def create_instance_id(obj: ty.Any) -> int:
    last_instance_id = getattr(obj.__class__, "_last_instance_id", 0)
    new_instance_id = last_instance_id + 1
    setattr(obj, "_instance_id", new_instance_id)
    setattr(obj.__class__, "_last_instance_id", new_instance_id)
    return new_instance_id


def instance_id(obj: ty.Any) -> int | None:
    return getattr(obj, "_instance_id", None)

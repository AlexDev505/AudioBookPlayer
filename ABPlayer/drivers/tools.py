from __future__ import annotations
from bs4 import BeautifulSoup
import json
import os
import re
import subprocess
import typing as ty
import eyed3
from bs4 import BeautifulSoup


if ty.TYPE_CHECKING:
    from pathlib import Path


class NotImplementedVariable:
    """
    >>> class A:
    ...     var = NotImplementedVariable()
    >>> class B(A): ...
    >>> class C(A):
    ...     var = 1
    >>> B.var
    NotImplementedError
    >>> C.var
    1
    """

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
    """
    :param file_path: Путь к аудио файлу.
    :returns: Длительность аудио файла в секундах.
    """
    result = subprocess.check_output(
        rf'{os.environ["FFPROBE_PATH"]} -v quiet -show_streams -of json "{file_path}"',
        shell=True,
    ).decode()
    fields = json.loads(result)["streams"][0]
    return float(fields["duration"])


def safe_name(text: str) -> str:
    """
    Убирает или заменяет символы не допустимые для имени файла Windows.
    """
    while text.count('"') >= 2:
        text = re.sub(r'"(.*?)"', r"«\g<1>»", text)
    return re.sub(r'[\\/:*?"<>|+]', "", text).rstrip(". ")


def create_instance_id(obj: ty.Any) -> int:
    """
    Создает идентификатор экземпляра.
    >>> class A:
    ...     def __init__(self):
    ...         create_instance_id(self)
    >>> a1 = A()
    >>> a2 = A()
    >>> instance_id(a1)
    1
    >>> instance_id(a2)
    2
    """
    last_instance_id = getattr(obj.__class__, "_last_instance_id", 0)
    new_instance_id = last_instance_id + 1
    setattr(obj, "_instance_id", new_instance_id)
    setattr(obj.__class__, "_last_instance_id", new_instance_id)
    return new_instance_id


def instance_id(obj: ty.Any) -> int | None:
    """
    :returns: Идентификатор экземпляра.
    """
    return getattr(obj, "_instance_id", None)


def html_to_text(html):
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text()


def hms_to_sec(length: str) -> int:
    """
    Converts the length of the audio file of format hh:mm:ss or ss or mm:ss to seconds.

    """
    parts = length.split(":")
    parts = [int(part) for part in parts]

    if len(parts) == 1:
        # Only seconds
        return parts[0]
    elif len(parts) == 2:
        # Minutes and seconds
        minutes, seconds = parts
        return minutes * 60 + seconds
    elif len(parts) == 3:
        # Hours, minutes, and seconds
        hours, minutes, seconds = parts
        return hours * 3600 + minutes * 60 + seconds
    else:
        raise ValueError("Invalid length format")

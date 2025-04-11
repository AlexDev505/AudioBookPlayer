from __future__ import annotations

import hashlib
import math
import re
import typing as ty

import pygments.formatters
import pygments.lexers
from loguru import logger


if ty.TYPE_CHECKING:
    from pathlib import Path
    from models.book import Book


class Version:
    revisions = [None, "rc", "betta", "alpha"]

    def __init__(
        self,
        major: int,
        minor: int,
        patch: int,
        revision: str = None,
        revision_number: int = None,
    ):
        self.major = major
        self.minor = minor
        self.patch = patch
        self.revision = revision
        self.revision_number = revision_number
        if revision not in self.revisions:
            raise ValueError(
                f"Unknown revision `{revision}`. it can be {self.revisions}"
            )

    @classmethod
    def from_str(cls, string_version: str) -> Version:
        if match := re.fullmatch(
            r"(\d+).(\d+).(\d+)(-(\S+).(\d+))?",
            string_version,
        ):
            return Version(
                int(match.group(1)),
                int(match.group(2)),
                int(match.group(3)),
                match.group(5),
                int(match.group(6)) if match.group(6) is not None else None,
            )
        raise ValueError(f"Can`t parse version from string: {string_version}")

    def to_str(self, revision: bool = True) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if revision and self.revision:
            version += f"-{self.revision}.{self.revision_number}"
        return version

    @property
    def is_stable(self) -> bool:
        return self.revision is None

    def __eq__(self, other: Version):
        return str(self) == str(other)

    def __gt__(self, other: Version):
        if self.to_str(False) != other.to_str(False):
            return self.to_str(False) > other.to_str(False)
        self_revision_index = Version.revisions.index(self.revision)
        other_revision_index = Version.revisions.index(other.revision)
        if self_revision_index != other_revision_index:
            return self_revision_index < other_revision_index
        return self.revision_number > other.revision_number

    def __repr__(self):
        return self.to_str()

    __str__ = __repr__


def convert_from_bytes(bytes_value: int) -> str:
    """
    :param bytes_value: The number of bytes.
    :returns: line of view <number> <unit of measurement>
    """
    if bytes_value == 0:
        return "0B"
    size_name = ("б", "КБ", "МБ", "ГБ", "ТБ", "ПБ", "EB", "ZB", "YB")
    i = int(math.floor(math.log(bytes_value, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_value / p, 2)
    return "%s %s" % (s, size_name[i])


def get_file_hash(file_path: ty.Union[str, Path], hash_func=hashlib.sha256) -> str:
    """
    :param file_path: The Way to the File.
    :param hash_func: hash function.
    :returns: hash file.
    """
    hash_func = hash_func()  # Initialize the hash function
    with open(file_path, "rb") as file:
        # We read the file by blocks in 64kb,
        # to avoid loading large files into RAM
        for block in iter(lambda: file.read(65536), b""):
            hash_func.update(block)
    file_hash = hash_func.hexdigest()
    logger.opt(colors=True).trace(
        f"{hash_func.name} of {str(file_path)}: <y>{file_hash}</y>"
    )
    return file_hash


def pretty_view(
    obj: ty.Any, *, multiline: bool = False, indent: int = 4, __finish=True
) -> str:
    """
    Creates a readable representation of a list/dictionary.
    :returns: String.
    """
    result = ""

    if isinstance(obj, (dict, list, tuple)):
        if isinstance(obj, dict):
            new_line = (
                "\n"
                if multiline
                and (
                    len(obj) > 4
                    or any(
                        isinstance(x, (dict, list, tuple)) and len(x) > 4
                        for x in obj.values()
                    )
                )
                else ""
            )
            brackets = ("{", "}")
            lines_iter = (
                f'"{key}": {pretty_view(value, multiline=multiline, __finish=False)}'
                for key, value in obj.items()
            )
        else:
            new_line = (
                "\n"
                if multiline
                and (
                    len(obj) > 7 or any(isinstance(x, (dict, list, tuple)) for x in obj)
                )
                else ""
            )
            brackets = ("[", "]")
            lines_iter = (
                pretty_view(item, multiline=multiline, __finish=False) for item in obj
            )

        result += f"{brackets[0]}{new_line}"
        lines = f", {new_line}".join(lines_iter)
        if "\n" in lines:
            lines = " " * indent + lines
            lines = lines.replace("\n", "\n" + " " * indent)
        result += lines
        result += f"{new_line}{brackets[1]}"
    elif obj is None:
        result = f"null"
    elif isinstance(obj, bool):
        result = f"{obj}".lower()
    elif isinstance(obj, (int, float)):
        result = f"{obj}"
    elif isinstance(obj, str):
        obj = obj.replace("\n", "\\n").replace("\r", "\\r").replace('"', '\\"')
        result = f'"{obj}"'

    if __finish:
        result = pygments.highlight(
            result,
            pygments.lexers.JsonLexer(),  # noqa
            pygments.formatters.TerminalFormatter(),  # noqa
        ).strip()
    return result


def make_book_preview(book: Book) -> dict:
    """
    :param book: Instance of the book.
    :returns: Dictionary with the main fields of the book.
    """
    return dict(
        author=book.author,
        name=book.name,
        series_name=book.series_name,
        number_in_series=book.number_in_series,
        reader=book.reader,
        duration=book.duration,
        url=book.url,
        preview=book.preview,
        driver=book.driver,
    )

from __future__ import annotations

import os
import sys
import typing as ty
from functools import cached_property
from pathlib import Path

from loguru import logger

logger.remove(0)
logger.add(sys.stdout, format="<lvl><n>{message}</n></lvl>", level=0)

FOLDERS = []
ADDITIONAL_FILE_EXTENSIONS = [".js", ".html", ".css"]
ADDITIONAL_EXCLUDE = ["plyr"]

EXCLUDE = [
    "build",
    "venv",
    "env",
    ".git",
    ".idea",
    "__pycache__",
    *ADDITIONAL_EXCLUDE,
]
EXTENSIONS = [".py", *ADDITIONAL_FILE_EXTENSIONS]


class DirData:
    def __init__(self, dir_name: str):
        self.dir_name = dir_name
        self.files: list[Path] = []
        self.rows: list[int] = []
        self.symbols: list[int] = []
        self.rows_without_docstrings: list[int] = []
        self.sizes: list[int] = []
        self.additional_files_data = {}
        self.included_dirs: list[DirData] = []

    def add_file_data(self, file: FileData) -> None:
        self.files.append(file.path)
        self.rows.append(file.rows)
        self.symbols.append(file.symbols)
        self.rows_without_docstrings.append(file.rows_without_docstrings)
        self.sizes.append(file.size)

    def add_additional_file_data(self, file: FileData) -> None:
        if (ext := file.path.suffix) not in self.additional_files_data:
            self.additional_files_data[ext] = {
                "count": 0,
                "rows": 0,
                "symbols": 0,
                "size": 0,
            }
        self.additional_files_data[ext]["count"] += 1
        self.additional_files_data[ext]["rows"] += file.rows
        self.additional_files_data[ext]["symbols"] += file.symbols
        self.additional_files_data[ext]["size"] += file.size

    def include_dir_data(self, dir_data: DirData) -> None:
        self.included_dirs.append(dir_data)
        self.files.extend(dir_data.files)
        self.rows.extend(dir_data.rows)
        self.symbols.extend(dir_data.symbols)
        self.rows_without_docstrings.extend(dir_data.rows_without_docstrings)
        self.sizes.extend(dir_data.sizes)
        for ext in dir_data.additional_files_data:
            if ext not in self.additional_files_data:
                self.additional_files_data[ext] = {
                    "count": 0,
                    "rows": 0,
                    "symbols": 0,
                    "size": 0,
                }
            self_ext_data = self.additional_files_data[ext]
            other_ext_data = dir_data.additional_files_data[ext]
            self_ext_data["count"] += other_ext_data["count"]
            self_ext_data["rows"] += other_ext_data["rows"]
            self_ext_data["symbols"] += other_ext_data["symbols"]
            self_ext_data["size"] += other_ext_data["size"]

    @cached_property
    def files_count(self) -> int:
        return len(self.files)

    @cached_property
    def rows_count(self) -> int:
        return sum(self.rows)

    @cached_property
    def symbols_count(self) -> int:
        return sum(self.symbols)

    @cached_property
    def rows_without_docstrings_count(self) -> int:
        return sum(self.rows_without_docstrings)

    @cached_property
    def docstrings_rows_count(self) -> int:
        return self.rows_count - self.rows_without_docstrings_count

    @cached_property
    def size(self) -> int:
        return sum(self.sizes)

    @cached_property
    def average_rows_count(self) -> int:
        return self.rows_count // self.files_count

    @cached_property
    def max_rows_count(self) -> int:
        return max(self.rows)

    @cached_property
    def file_with_max_rows_count(self) -> Path:
        return self.files[self.rows.index(self.max_rows_count)]

    @cached_property
    def max_rows_without_docstrings_count(self) -> int:
        return max(self.rows_without_docstrings)

    @cached_property
    def file_without_docstrings_with_max_rows_count(self) -> Path:
        return self.files[
            self.rows_without_docstrings.index(
                self.max_rows_without_docstrings_count
            )
        ]

    @cached_property
    def biggest_module(self) -> DirData:
        return max(self.included_dirs, key=lambda x: x.rows_count)

    def log(self) -> None:
        logger.opt(colors=True).info(
            f"\n\t<g><b>{self.dir_name} summary</b></g>\n"
            f"Всего файлов: <e>{self.files_count}</e>\n"
            f"Всего строк: <e>{self.rows_count}</e>\n"
            f"Всего строк (без комментариев): "
            f"<e>{self.rows_without_docstrings_count}</e>\n"
            f"Всего символов: <e>{self.symbols_count}</e>\n"
            f"Всего строк комментариев: <e>{self.docstrings_rows_count}</e>\n"
            f"Общий размер: <e>{convert(self.size)}</e>\n"
            f"Среднее кол-во строк: <e>{self.average_rows_count}</e>\n"
            f"Максимальное кол-во строк: <e>{self.max_rows_count}</e> "
            f"(<g>{self.file_with_max_rows_count}</g>)\n"
            f"Максимальное кол-во строк (без комментариев): "
            f"<e>{self.max_rows_without_docstrings_count}</e> "
            f"(<g>{self.file_without_docstrings_with_max_rows_count}</g>)"
            + (
                "\n"
                + "\n".join(
                    f"<e>{value['count']}</e> <y>{ext}</y> files: "
                    f"<e>{value['rows']}</e> строк, <e>{convert(value['size'])}</e>"
                    for ext, value in self.additional_files_data.items()
                )
                if self.additional_files_data
                else ""
            )
            + (
                (
                    f"\nСамый большой модуль: <g>{self.biggest_module.dir_name}</g> "
                    f"(<e>{self.biggest_module.rows_count}</e> строк)"
                )
                if self.included_dirs
                else ""
            )
            + "\n"
        )


class FileData(ty.NamedTuple):
    path: Path
    rows: int
    symbols: int
    rows_without_docstrings: int
    size: int

    def log(self) -> None:
        logger.opt(colors=True).info(
            f"\t<g>{self.path}</g>\n"
            f"Кол-во строк: <e>{self.rows}</e>\n"
            f"Кол-во строк (без комментариев): <e>{self.rows_without_docstrings}</e>\n"
            f"Кол-во символов: <e>{self.symbols}</e>\n"
            f"Размер: <e>{convert(self.size)}</e>\n"
        )


def convert(x: int) -> str:
    """
    Конвертирует число битов в другие.
    """
    x /= 1024
    _i = ["Кб", "Мб", "Гб"]
    i = 0
    while x > 1024:
        x /= 1024
        i += 1
    return "{:.2f} {}".format(x, _i[i])


def path_filter(path: Path) -> bool:
    if FOLDERS:
        return any(folder in str(path) for folder in FOLDERS)
    if any(exclude in str(path) for exclude in EXCLUDE):
        return False
    if path.is_file():
        return path.suffix in EXTENSIONS
    return True


def handle_file(path: Path) -> FileData:
    size = os.path.getsize(path)
    with open(path, encoding="utf-8") as f:
        data = f.read()
        symbols = len(data)
        f_data = list(map(str.strip, data.splitlines()))
        rows = len(f_data) + 1
        rows_without_docstrings = 0

        if path.suffix == ".py":
            start_i = -1
            while '"""' in f_data:
                if start_i == -1:
                    start_i = f_data.index('"""')
                    f_data[start_i] = ""
                    if not (start_i == 0 or f_data[start_i - 1].endswith(":")):
                        continue
                else:
                    end_i = f_data.index('"""')
                    f_data[start_i : end_i + 1] = []
                    start_i = -1
            rows_without_docstrings = len(f_data) + 1

    return FileData(path, rows, symbols, rows_without_docstrings, size)


def handle_dir(path: Path, log_files: bool = False) -> DirData:
    data = DirData(path.name)

    for root, dirs, files in os.walk(path):
        for file in files:
            file_path = Path(os.path.join(root, file))
            if not path_filter(file_path):
                continue
            file_data = handle_file(file_path)
            if log_files:
                file_data.log()
            if file_path.suffix == ".py":
                data.add_file_data(file_data)
            else:
                data.add_additional_file_data(file_data)

    return data


def rows_count(log_dirs: bool = False, log_files: bool = False):
    all_dirs: list[Path] = []
    for root, dirs, _ in os.walk("."):
        all_dirs = [
            Path(f"{root}/{path}") for path in dirs if path_filter(Path(path))
        ]
        break

    data = DirData("Total")
    for dir_path in all_dirs:
        dir_data = handle_dir(dir_path, log_files)
        if not dir_data.files_count:
            continue
        if log_dirs:
            dir_data.log()
        data.include_dir_data(dir_data)

    data.log()


if __name__ == "__main__":
    rows_count(log_dirs=True, log_files=False)

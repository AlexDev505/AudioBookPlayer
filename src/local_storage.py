from __future__ import annotations

import os
import re
import shutil
import traceback
import typing as ty
from contextlib import suppress
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import orjson
from loguru import logger

from models.book import (
    AudioBook,
    Book,
    BookData,
    BookStatus,
    Chapter,
    Chapters,
    ListeningProgress,
    SourceType,
    TextBook,
)
from tools import (
    duration_sec_to_str,
    get_audio_file_duration,
    get_file_hash,
    pretty_view,
)

if ty.TYPE_CHECKING:
    from models.book import BookSource, RawBook

FILE_NAME = ".dibook"


def save(book: Book, source: BookSource) -> None:
    """
    Saves the book to a `FILE_NAME` file.
    """
    dibook_path = book.dir_path / source.dir_path / FILE_NAME
    with open(dibook_path, "wb") as file:
        file.write(orjson.dumps(_book_to_dump(book, source)))
    logger.opt(colors=True).debug(
        f"{book:colored} saved to <r>{FILE_NAME}</r>: <y>{dibook_path}</y>"
    )


def check_exists(book: Book, source: BookSource) -> bool:
    return os.path.isfile(book.dir_path / source.dir_path / FILE_NAME)


def load(path: Path) -> tuple[Book, BookSource] | None:
    """
    Loads a book from a `FILE_NAME` file.
    :returns: The loaded book, or `None` if the file does not exist.
    """
    logger.opt(colors=True).trace(
        f"loading data from <r>{FILE_NAME}</r> <y>{path}</y>"
    )
    try:
        with open(path, "rb") as file:
            data = orjson.loads(file.read())
        if data.get("ignore"):
            logger.opt(colors=True).trace(f"<y>{path}</y> marked as ignored")
            return
        stype = data["source"].pop("type")
        data["source"]["status"] = BookStatus(data["source"]["status"])
        if chapters := data["source"].get("chapters"):
            data["source"]["chapters"] = Chapters(chapters)
        if (
            progress := data["source"].get("progress")
        ) and stype == "AudioBook":
            data["source"]["progress"] = ListeningProgress(**progress)
        source = SourceType[stype].value(**data["source"])
        del data["source"]

        data["status"] = BookStatus(data["status"])
        data["adding_date"] = datetime.fromisoformat(data["adding_date"])
        book = Book(**data)
        if not str(path.parent).endswith(
            book_path := str(book.book_path / source.dir_path)[2:]
        ):
            logger.opt(colors=True).debug(
                f"incorrect <r>{FILE_NAME}</r> file path <y>{path}</y> "
                f"it's not ends on <y>{book_path}</y>"
            )
            return

        logger.opt(lazy=True).trace(
            "{file_name} loaded: book={book} source={source}",
            file_name=lambda: FILE_NAME,
            book=lambda book=book: pretty_view(
                book.asdict(),
                multiline=not os.getenv("NO_MULTILINE", False),
            ),
            source=lambda source=source: pretty_view(
                source.asdict(),
                multiline=not os.getenv("NO_MULTILINE", False),
            ),
        )

        return book, source

    except Exception as err:
        logger.opt(colors=True).debug(
            f"error while loading book from <r>{FILE_NAME}</r> <y>{path}</y> : "
            f"<lr>{type(err).__name__}: {err}</lr>"
        )
        logger.trace(traceback.format_exc())


def handle_self_loaded_audio(
    root: Path, dir_path: Path, file_names: list[str]
) -> tuple[Book, AudioBook] | None:
    book_dir = root.relative_to(dir_path)
    logger.opt(colors=True).debug(f"trying to load book from <y>{book_dir}</y>")
    if not (match := _parse_id_parts(book_dir)):
        return
    title, author, series_name, number_in_series, source_tag = match

    chapters: list[Chapter] = []
    files: dict[str, str] = {}

    total_duration = 0
    next_index = 0
    for file_name in sorted(file_names):
        if not file_name.endswith(".mp3"):
            continue
        if match := re.fullmatch(r"([0-9]+)\. (.+)\.mp3", file_name):
            item_title = match.group(2)
        else:
            item_title = file_name

        file_path = root / file_name
        duration = get_audio_file_duration(file_path)
        total_duration += duration
        files[file_name] = get_file_hash(file_path)
        chapters.append(
            Chapter(
                title=item_title,
                url="",
                file_index=next_index,
                start_time=0,
                end_time=int(duration),
            )
        )
        next_index += 1

    book = Book(
        title=title,
        author=author,
        series_name=series_name,
        number_in_series=number_in_series,
        description="",
        cover="",
    )
    source = AudioBook(
        url=f"file://{root / FILE_NAME}",
        cover="",
        files=files,
        narrator=source_tag,
        duration=duration_sec_to_str(int(total_duration)),
        chapters=ty.cast(Chapters, chapters),
    )
    save(book, source)
    return book, source


def handle_self_loaded_text(
    root: Path, dir_path: Path, file_names: list[str]
) -> tuple[Book, TextBook] | None:
    pass


def scan(path: str) -> ty.Generator[tuple[Book, BookSource], ty.Any, None]:
    """
    Scans the directory for `FILE_NAME` files.
    :returns: Generator of raw book instances loaded from found files.
    """
    logger.opt(colors=True).debug(
        f"scanning <y>{path}</y> for <r>{FILE_NAME}</r>"
    )
    books_found = 0
    for root, _, file_names in os.walk(path):
        if FILE_NAME in file_names:
            dibook_path = (root := Path(root)) / FILE_NAME
            if not (loaded := load(dibook_path)):
                if not mark_as_ignore(root):
                    with suppress(OSError):
                        os.remove(dibook_path)
                continue
            books_found += 1
            yield loaded
        elif any(file_name.endswith(".mp3") for file_name in file_names):
            if loaded := handle_self_loaded_audio(
                Path(root), Path(path), file_names
            ):
                books_found += 1
                yield loaded
        elif any(
            file_name.endswith(".epub") or file_name.endswith(".fb2")
            for file_name in file_names
        ):
            if loaded := handle_self_loaded_text(
                Path(root), Path(path), file_names
            ):
                books_found += 1
                yield loaded

    logger.opt(colors=True).debug(f"books found: <y>{books_found}</y>")


def _book_to_dump(book: Book, source: BookSource) -> dict[str, ty.Any]:
    source_data = source.asdict()
    del (
        source_data["sid"],
        source_data["local_cover"],
        source_data["selected"],
        source_data["progress_percent"],
        source_data["downloaded"],
        source_data["domain"],
    )
    source_data["files"] = source.files
    return dict(
        **BookData.asdict(book),
        cover=book.cover,
        adding_date=book.adding_date.isoformat(),
        favorite=book.favorite,
        status=book.status.value,
        source=dict(
            type=source.__class__.__name__,
            **source_data,
        ),
    )


def _set(
    path: Path,
    book: dict[str, ty.Any] | None = None,
    source: dict[str, ty.Any] | None = None,
) -> bool:
    try:
        with open(path, "rb") as file:
            data = orjson.loads(file.read())
        if book is not None:
            data.update(book)
        if source is not None:
            data["source"].update(source)
        with open(path, "wb") as out:
            out.write(orjson.dumps(data))
    except (orjson.JSONDecodeError, OSError):
        return False
    return True


def mark_as_ignore(path: Path) -> bool:
    return _set(path / FILE_NAME, book={"ignore": True})


def set_status(path: Path, status: BookStatus) -> bool:
    return _set(
        path / FILE_NAME,
        book={"status": status.value},
        source={"status": status.value},
    )


def set_listening_progress(path: Path, lp: ListeningProgress) -> bool:
    return _set(path / FILE_NAME, source={"progress": asdict(lp)})


def set_reading_progress(path: Path, cfi: str, percent: int) -> bool:
    return _set(
        path / FILE_NAME,
        source={"progress": cfi, "progress_percent": percent},
    )


def _parse_id_parts(path: Path) -> tuple[str, str, str, str, str] | None:
    id_parts = path.parts
    logger.opt(colors=True).debug(f"trying to load book from <y>{path}</y>")
    title = author = series_name = number_in_series = source_tag = ""
    if len(id_parts) == 1:
        # /title
        title = id_parts[0]
    elif len(id_parts) == 2:
        # /author/title
        author = id_parts[0]
        title = id_parts[1]
    elif len(id_parts) == 3:
        # /author/title/source_tag
        author = id_parts[0]
        title = id_parts[1]
        source_tag = id_parts[2]
    elif len(id_parts) == 4:
        # /author/series/number_in_series. title/source_tag
        author = id_parts[0]
        series_name = id_parts[1]
        if match := re.fullmatch(r"([0-9.\-]+)\. (.+)", id_parts[2]):
            title, number_in_series = match.group(2), match.group(1)
        else:
            title = id_parts[2]
        source_tag = id_parts[3]
    else:
        return None
    return title, author, series_name, number_in_series, source_tag


def move(old_path: Path, new_path: Path, file_names: list[str]) -> bool:
    for file_name in [*file_names, FILE_NAME, "cover.jpg"]:
        try:
            shutil.move(old_path / file_name, new_path / file_name)
            logger.opt(colors=True).trace(f"file <y>{file_name}</y> moved")
        except OSError as err:
            logger.error(
                f"failed on moving {file_name}. {type(err).__name__}: {err}"
            )
            logger.trace(traceback.format_exc())
            return False
    with suppress(IOError):
        os.removedirs(old_path)
    return True


def delete(path: Path, file_names: list[str]) -> bool:
    for file in [*file_names, FILE_NAME, "cover.jpg"]:
        file_path = path / file
        try:
            logger.opt(colors=True).trace(f"deleting <y>{file_path}</y>")
            os.remove(file_path)
        except OSError as err:
            logger.error(
                f"failed on deleting {file_path}. {type(err).__name__}: {err}"
            )
            logger.trace(traceback.format_exc())
            return False
    with suppress(OSError):
        os.removedirs(path)
    return True

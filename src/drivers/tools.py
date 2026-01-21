import asyncio
import os
import re
import subprocess
import types as tys
import typing as ty
from abc import ABC, abstractmethod
from contextlib import suppress
from enum import Enum
from pathlib import Path

from bs4 import BeautifulSoup, Tag
from loguru import logger

from models.book import BookSource


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


class IOTasksManager:
    """
    Asynchronous task manager
    Implements a queue and limits the number of simultaneously executing tasks
    Executes all tasks from `tasks_generator`
    """

    def __init__(self, max_tasks: int = 1):
        self._max_tasks: int = max_tasks
        self._tasks_count: int = 0
        self._tasks_generator: ty.Generator[ty.Coroutine] | None = None
        self._future: asyncio.Future | None = None
        self._tasks: list[asyncio.Task] = []

    def execute_tasks_factory(
        self, tasks_generator: ty.Generator[ty.Coroutine]
    ) -> None:
        """
        Setups `tasks_generator` and waits for finishing
        """
        asyncio.run(self.wait_finishing(tasks_generator))

    async def wait_finishing(
        self, tasks_generator: ty.Generator[ty.Coroutine]
    ) -> None:
        """
        Setups `tasks_generator`, creates start tasks pool and waits for finishing
        """
        if self._tasks_generator:
            raise RuntimeError("This `IOTasksManager` is busy")
        self._tasks_generator = tasks_generator
        self._future = asyncio.Future()
        for _ in range(self._max_tasks):
            self._run_next()
        with suppress(asyncio.CancelledError):
            await self._future

    def _run_next(self) -> None:
        """
        Starts the next task
        """
        if not self._tasks_generator:
            return
        if coro := next(self._tasks_generator, None):
            self._tasks_count += 1
            self._tasks.append(t := asyncio.create_task(coro))
            t.add_done_callback(self._task_done_callback)
        elif self._tasks_count == 0:
            asyncio.create_task(self.terminate())

    def _task_done_callback(self, t: asyncio.Task) -> None:
        """
        Calls when task is done
        Starts the next task
        """
        self._tasks.remove(t)
        self._tasks_count -= 1
        self._run_next()

    async def terminate(self) -> None:
        """
        Stops running next tasks
        """
        if self._future:
            self._tasks_generator = None
            for t in self._tasks:
                t.cancel()
            self._future.cancel()
            self._future = None
        while self._tasks_count:
            await asyncio.sleep(0.01)


class BaseProgressHandler[Statuses: Enum](ABC):
    """
    Progress handler.
    Abstract class for handling progress updates.
    >>> N: int = 10
    >>> process_handler = BaseProgressHandler()
    >>> process_handler.init(Statuses.preparing_data)
    >>> data = list(range(N))
    >>> process_handler.init(Statuses.processing, total_count=N)
    >>> for _ in data:
    ...     process_handler.progress(1)
    >>> process_handler.init(Statuses.finished)
    """

    DEFAULT_STATUS: Statuses | None = None
    """ Status that is used when instance created """

    def __init__(self):
        self._status: Statuses | None = self.DEFAULT_STATUS
        self._total_count: int | None = None
        self._done_count: int | None = None
        create_instance_id(self)
        logger.opt(colors=True).trace(f"{self:colored} created")

    @property
    def status(self) -> Statuses | None:
        return self._status

    def init_status(
        self, status: Statuses, total_count: int | None = None
    ) -> None:
        self._status = status
        self._total_count = total_count
        self._done_count = None if total_count is None else 0
        logger.opt(colors=True).trace(
            f"{self:colored} - <y>{status.value}</y>"
            + (f" total_size=<y>{total_count}</y>" if total_count else "")
        )

    def progress(self, count: int) -> None:
        if self._done_count is None:
            raise RuntimeError(f"{self:colored} has a non-countable status")
        self._done_count += count
        self.show_progress()

    def set_done_count(self, count: int) -> None:
        if self._total_count is None:
            raise RuntimeError(f"{self:colored} has a non-countable status")
        self._done_count = count
        self.show_progress()

    @abstractmethod
    def show_progress(self) -> None:
        """
        Displays the progress.
        """

    def __repr__(self):
        return f"PH-{instance_id(self)}"

    def __format__(self, format_spec):
        if format_spec == "colored":
            return f"<y>{self!r}</y>"
        return repr(self)


def prepare_file_metadata(
    file_path: Path,
    chapter_index: int,
    author: str,
    title: str,
    series_name: str,
) -> None:
    """
    Prepares file metadata
    # TODO
    """


def fix_m4a_meta(file_path: Path) -> None:
    """
    Fixes m4a file metadata.
    """
    output_path = str(file_path)
    file_path = file_path.rename(
        Path(file_path.parent, file_path.name.removesuffix(".m4a") + "-old.m4a")
    )
    subprocess.check_output(
        f"{os.environ['FFMPEG_PATH']} -y -v quiet "
        f'-i "{file_path}" -acodec copy "{output_path}"',
        shell=True,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    os.remove(file_path)


def merge_ts_files(
    ts_file_paths: list[Path],
    output_dir: Path,
    output_file_name: str,
) -> None:
    """
    Merges ts files to one.
    """
    input_fp = output_dir / (output_file_name + ".txt")
    with open(input_fp, "w") as f:
        f.write("\n".join(map(lambda x: f"file '{x.name}'", ts_file_paths)))
    output_file_path = output_dir / (output_file_name + ".mp3")

    result = subprocess.check_output(
        f"{os.environ['FFMPEG_PATH']} -y -v quiet -f concat -safe 0 "
        f'-i "{output_file_name + ".txt"}" -map 0:a -c:a libmp3lame '
        f'"{output_file_path}"',
        cwd=output_file_path.parent,
        shell=True,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    ).decode("cp866")
    if result:
        logger.debug(result)
    os.remove(input_fp)


def convert_ts_to_mp3(ts_file_path: Path, mp3_file_path: Path) -> None:
    """
    Converts ts files to mp3 by ffmpeg.
    """
    subprocess.check_output(
        f'{os.environ["FFMPEG_PATH"]} -y -v quiet -i "{ts_file_path}" -vn '
        f'"{mp3_file_path}"',
        shell=True,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )


def split_ts(ts_file_path: Path, on: int) -> tuple[Path, Path]:
    """
    Splits one ts file at `on` sec.
    Creates two new files with same names and suffixes `-1` and `-2`.
    """
    first_part = Path(
        os.path.join(
            ts_file_path.parent, f"{ts_file_path.name.removesuffix('.ts')}-1.ts"
        )
    )
    second_part = Path(
        os.path.join(
            ts_file_path.parent, f"{ts_file_path.name.removesuffix('.ts')}-2.ts"
        )
    )
    result = subprocess.check_output(
        f'{os.environ["FFMPEG_PATH"]} -y -v quiet -i "{ts_file_path}" -to {on} -c copy '
        f'"{first_part}"',
        shell=True,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    ).decode("cp866")
    if result:
        logger.debug(result)
    result = subprocess.check_output(
        f'{os.environ["FFMPEG_PATH"]} -y -v quiet -i "{ts_file_path}" -ss {on} -c copy '
        f'"{second_part}"',
        shell=True,
        stdin=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    ).decode("cp866")
    if result:
        logger.debug(result)
    return first_part, second_part


def safe_name(text: str) -> str:
    """
    Removes or replaces characters not allowed in Windows file names.
    """
    while text.count('"') >= 2:
        text = re.sub(r'"(.*?)"', r"«\g<1>»", text)
    return re.sub(r'[\\/:*?"<>|+]', "", text).rstrip(". ")


def get_source_type(cls):
    """
    Gets and validates the source type from the class generic args
    :returns: instance of `BookSource` or tuple of `BookSource` instances
    """
    source_types = ty.get_args(tys.get_original_bases(cls)[0])
    if not source_types:
        raise NotImplementedError(
            f"book source type not specified in class `{cls.__name__}`"
        )
    if isinstance(source_types[0], (ty.Union, tys.UnionType)):
        source_types = ty.get_args(source_types)
    for source_type in source_types:
        if issubclass(source_type, BookSource):
            raise TypeError(
                f"expected BookSource, got {source_type} "
                f"in class `{cls.__name__}`"
            )
    return source_types[0] if len(source_types) == 1 else source_types


def create_instance_id(obj: ty.Any) -> int:
    """
    Creates an instance identifier
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
    :returns: Instance identifier
    """
    return getattr(obj, "_instance_id", None)


def html_to_text(html: str) -> str:
    """
    Fetches all text from HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text()


def find_in_soup(
    soup: Tag,
    selector: str,
    default: str = "",
    modification: ty.Callable[[str], str] = str.strip,
) -> str:
    if el := soup.select_one(selector):
        return modification(el.text)
    return default

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import typing as ty
from contextlib import suppress
from pathlib import Path

import eyed3
from bs4 import BeautifulSoup
from loguru import logger


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
    Executes all tasks from `_tasks_generator`
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
        Setups `_tasks_generator` and waits for finishing
        """
        asyncio.run(self.wait_finishing(tasks_generator))

    async def wait_finishing(
        self, tasks_generator: ty.Generator[ty.Coroutine]
    ) -> None:
        """
        Setups `_tasks_generator`, creates start tasks pool and waits `_future`
        """
        if self._tasks_generator:
            raise RuntimeError("Tasks are already running")
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
        Calls when task is done.
        Starts the next task.
        """
        self._tasks.remove(t)
        self._tasks_count -= 1
        self._run_next()

    async def terminate(self) -> None:
        """
        Stops running next tasks.
        """
        if self._future:
            self._future.cancel()
            self._future = None
            self._tasks_generator = None
            for t in self._tasks:
                t.cancel()
        while self._tasks_count:
            await asyncio.sleep(0.01)


def prepare_file_metadata(
    file_path: ty.Union[str, Path],
    author: str,
    title: str,
    item_index: int,
) -> None:
    """
    Modifies the metadata of the audio file.
    :param file_path: Path to the audio file.
    :param author: Author of the book.
    :param title: Title of the chapter.
    :param item_index: Sequential number of the file.
    """
    if not str(file_path).endswith(".mp3"):
        return
    file = eyed3.load(file_path)
    file.initTag()
    file.tag.title = title
    file.tag.artist = author
    file.tag.track_num = item_index + 1
    file.tag.save()


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


def create_instance_id(obj: ty.Any) -> int:
    """
    Creates an instance identifier.
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
    :returns: Instance identifier.
    """
    return getattr(obj, "_instance_id", None)


def html_to_text(html: str) -> str:
    """
    Fetches all text from HTML.
    """
    soup = BeautifulSoup(html, "html.parser")
    return soup.get_text()


def find_in_soup(
    soup: BeautifulSoup,
    selector: str,
    default: str = "",
    modification: ty.Callable[[str], str] = str.strip,
) -> str:
    if el := soup.select_one(selector):
        return modification(el.text)
    return default

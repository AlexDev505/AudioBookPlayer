from __future__ import annotations

import asyncio
import os
import re
import subprocess
import time
import typing as ty
from contextlib import suppress

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


class IOTasksManager:
    """
    Asynchronous task manager.
    Implements a queue and limits the number of simultaneously executing tasks.
    Executes all tasks from `_tasks_generator`.
    """

    def __init__(self, max_tasks: int = 1):
        self.max_tasks: int = max_tasks
        self.tasks_count: int = 0
        self._tasks_generator: ty.Generator[ty.Coroutine] | None = None
        self._future: asyncio.Future | None = None

    def execute_tasks_factory(
        self, tasks_generator: ty.Generator[ty.Coroutine]
    ) -> None:
        """
        Setups `_tasks_generator` and waits for finishing.
        """
        self._tasks_generator = tasks_generator
        asyncio.run(self._wait_finishing())

    def _run_next(self) -> None:
        """
        Starts the next task.
        """
        if not self._future:
            return
        if coro := next(self._tasks_generator, None):
            self.tasks_count += 1
            asyncio.create_task(coro).add_done_callback(self._task_done_callback)
        elif self.tasks_count == 0:
            self.terminate()

    def _task_done_callback(self, _: asyncio.Task) -> None:
        """
        Calls when task is done.
        Starts the next task.
        """
        self.tasks_count -= 1
        self._run_next()

    async def _wait_finishing(self) -> None:
        """
        Creates start tasks pool and waits `_future`
        """
        self._future = asyncio.Future()
        for _ in range(self.max_tasks):
            self._run_next()
        with suppress(asyncio.CancelledError):
            await self._future

    def terminate(self) -> None:
        """
        Stops running next tasks.
        """
        if self._future:
            self._future.cancel()
            self._future = None
        while self.tasks_count:
            time.sleep(0.01)


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
    file = eyed3.load(file_path)
    file.initTag()
    file.tag.title = title
    file.tag.artist = author
    file.tag.track_num = item_index + 1
    file.tag.save()


def get_audio_file_duration(file_path: Path) -> float:
    """
    :param file_path: Path to the audio file.
    :returns: Duration of the audio file in seconds.
    """
    result = subprocess.check_output(
        rf'{os.environ["FFMPEG_PATH"]} -v quiet -stats -i "{file_path}" -f null -',
        stderr=subprocess.STDOUT,
    ).decode()
    if not (
        match := re.search(
            r"time=(?P<h>\d+):(?P<m>\d{2}):(?P<s>\d{2}).(?P<ms>\d{2})", result
        )
    ):
        return 0
    return (
        int(match.group("h")) * 3600
        + int(match.group("m")) * 60
        + int(match.group("s"))
        + int(match.group("ms")) / 100
    )


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

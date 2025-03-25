from __future__ import annotations

import asyncio
import os
import re
import subprocess
import typing as ty
from functools import wraps

import eyed3


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
    """

    def __init__(self, max_tasks: int = 1):
        self.max_tasks: int = max_tasks
        self.tasks_count: int = 0
        self.planed_tasks_count: int = 0
        self.planed_coroutines: list[
            tuple[ty.Coroutine, ty.Callable[[asyncio.Task], None]]
        ] = []

    def add_task(
        self,
        coro: ty.Coroutine,
        callback: ty.Callable[[asyncio.Task], None],
    ) -> None:
        """
        Adds a task to the queue or runs it if there is a quota.
        """
        self.planed_tasks_count += 1
        self.planed_coroutines.append((coro, callback))
        if self.tasks_count < self.max_tasks and self.planed_tasks_count:
            self._run_next()

    def _run_next(self) -> None:
        """
        Start the next task.
        """
        coro, callback = self.planed_coroutines.pop(0)
        self.planed_tasks_count -= 1
        self.tasks_count += 1
        asyncio.create_task(coro).add_done_callback(
            self._task_callback_decorator(callback)
        )

    def _task_callback_decorator(
        self, callback: ty.Callable[[asyncio.Task], None]
    ) -> ty.Callable[[asyncio.Task], None]:
        """
        A wrapper for task callbacks that reduces the running task counter
        and starts tasks from the queue.
        """

        @wraps(callback)
        def _wrapper(task: asyncio.Task) -> None:
            callback(task)
            self.tasks_count -= 1
            if self.planed_tasks_count:
                self._run_next()

        return _wrapper


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

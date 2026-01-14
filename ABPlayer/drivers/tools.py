import asyncio
import re
import time
import typing as ty
from contextlib import suppress


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
            asyncio.create_task(coro).add_done_callback(
                self._task_done_callback
            )
        elif self._tasks_count == 0:
            self.terminate()

    def _task_done_callback(self, _: asyncio.Task) -> None:
        """
        Calls when task is done
        Starts the next task
        """
        self._tasks_count -= 1
        self._run_next()

    def terminate(self) -> None:
        """
        Stops running next tasks
        """
        if self._future:
            self._future.cancel()
            self._future = None
            self._tasks_generator = None
        while self._tasks_count:
            time.sleep(0.01)


def safe_name(text: str) -> str:
    """
    Removes or replaces characters not allowed in Windows file names
    """
    while text.count('"') >= 2:
        text = re.sub(r'"(.*?)"', r"«\g<1>»", text)
    return re.sub(r'[\\/:*?"<>|+]', "", text).rstrip(". ")


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

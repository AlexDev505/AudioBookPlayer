from __future__ import annotations

import asyncio
import typing as ty
from contextlib import suppress


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

from __future__ import annotations

import typing as ty
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from loguru import logger

from ..tools import IOTasksManager, create_instance_id, instance_id

if ty.TYPE_CHECKING:
    from models.book import BookSource


@dataclass
class File:
    index: int
    name: str
    url: str
    duration: float | None = None
    size: int | None = None
    extra: dict = field(default_factory=dict)


class DownloadProcessStatus(Enum):
    """
    Download progress statuses.
    """

    WAITING = "waiting"
    PREPARING = "preparing"
    DOWNLOADING = "downloading"
    FINISHING = "finishing"
    FINISHED = "finished"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


class BaseDownloadProcessHandler(ABC):
    """
    Download process handler.
    Visualizes the process.
    >>> N = 10
    >>> process_handler = BaseDownloadProcessHandler()
    >>> process_handler.init(N, status=DownloadProcessStatus.DOWNLOADING)
    >>> for _ in range(N):
    ...     process_handler.progress(1)
    >>> process_handler.finish()
    """

    def __init__(self):
        self.status = DownloadProcessStatus.WAITING
        self.total_size: int = 0
        self.done_size: int = 0
        create_instance_id(self)
        logger.opt(colors=True).trace(f"{self:styled} created")

    def init(self, total_size: int, status: DownloadProcessStatus) -> None:
        self.status = status
        self.total_size = total_size
        self.done_size = 0
        logger.opt(colors=True).trace(
            f"{self:styled} inited: "
            f"<y>{status.value}</y> total_size=<y>{total_size}</y>"
        )

    def progress(self, size: int) -> None:
        self.done_size += size
        self.show_progress()

    def finish(self) -> None:
        self.status = DownloadProcessStatus.FINISHED
        self.done_size = self.total_size
        logger.opt(colors=True).trace(f"{self:styled} finished")

    @abstractmethod
    def show_progress(self) -> None:
        """
        Displays the progress.
        """

    def __repr__(self):
        return f"DPH-{instance_id(self)}"

    def __format__(self, format_spec):
        if format_spec == "styled":
            return f"<y>{self!r}</y>"
        return repr(self)


class BaseDownloader[SourceT: BookSource](ABC):
    """
    File downloader.
    """

    def __init__(
        self,
        source: SourceT,
        destination: Path,
        process_handler: BaseDownloadProcessHandler | None = None,
    ):
        self.source = source
        self.destination = destination
        self.downloaded_files: dict[int, Path] = {}
        self.process_handler = process_handler
        self.tasks_manager = IOTasksManager(20)

        self._files: list[File] = []
        self._terminated: bool = False

        create_instance_id(self)
        logger.opt(colors=True).debug(
            f"{self!r} initialized. book: {destination}"
        )

    async def download(self):
        pass

    async def terminate(self):
        pass

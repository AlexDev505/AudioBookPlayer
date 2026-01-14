from __future__ import annotations

import asyncio
import typing as ty
from contextlib import suppress
from pathlib import Path

import orjson
from websockets.asyncio.server import serve

from ..base_driver import Driver
from .base_downloader import (
    BaseDownloader,
    BaseDownloadProcessHandler,
    DownloadProcessStatus,
)

if ty.TYPE_CHECKING:
    from websockets.asyncio.server import ServerConnection

__all__ = ["run_server"]

downloading_tasks: dict[int, BaseDownloader] = {}


async def send(ws: ServerConnection, event: str, **data: ty.Any) -> None:
    data.update({"event": event})
    await ws.send(orjson.dumps(data))


class ServerDPH(BaseDownloadProcessHandler):
    def __init__(self, ws: ServerConnection, sid: int):
        self.ws = ws
        self.sid = sid
        super().__init__()

    def init(self, total_size: int, status: DownloadProcessStatus) -> None:
        super().init(total_size, status)
        asyncio.create_task(self._init())

    async def _init(self):
        await send(
            self.ws,
            "init",
            sid=self.sid,
            status=self._status.value,
            total_size=self.total_size,
        )

    def progress(self, size: int) -> None:
        super().progress(size)
        asyncio.create_task(self._show_progress(size))

    async def _show_progress(self, size: int) -> None:
        await send(self.ws, "progress", sid=self.sid, size=size)

    def show_progress(self) -> None:
        pass

    @property
    def status(self) -> DownloadProcessStatus:
        return self._status

    @status.setter
    def status(self, v: DownloadProcessStatus):
        self._status = v
        asyncio.create_task(self._send_status())

    async def _send_status(self):
        await send(
            self.ws, "set_status", sid=self.sid, status=self._status.value
        )


async def download(
    ws: ServerConnection, source_data: dict[str, ty.Any], destination: str
) -> None:
    try:
        assert isinstance(
            driver := Driver.get_suitable_driver(source_data["source_url"]),
            Driver,
        )
        source = driver.source_type(**source_data)
    except (KeyError, AssertionError, TypeError):
        return

    downloader = downloading_tasks[source.id] = driver.downloader_factory(
        source, Path(destination), ServerDPH(ws, source.id)
    )
    await downloader.download()


async def handler(websocket: ServerConnection):
    async for message in websocket:
        with suppress(orjson.JSONDecodeError, AssertionError):
            data = orjson.loads(message)
            assert (command := data.get("command")) is not None
            if command == "download":
                assert isinstance(source := data.get("source"), dict)
                assert isinstance(destination := data.get("destination"), str)
                asyncio.create_task(download(websocket, source, destination))
            elif command == "get_downloads":
                pass
            elif command == "terminate":
                pass
            elif command == "shutdown":
                pass


async def run_server():
    async with serve(handler, "localhost", 8765) as server:
        await server.serve_forever()

from __future__ import annotations

import asyncio
import threading
import typing as ty
from contextlib import suppress

import orjson
from loguru import logger
from websockets.asyncio.server import serve
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

from database import Database
from models.book import SourceType

from ..base_downloader import (
    BaseDownloader,
    BaseDownloadingProgressHandler,
    DownloadProcessStatus,
)
from ..base_driver import BaseDriver
from .utils import get_downloading_id

if ty.TYPE_CHECKING:
    from websockets.asyncio.server import ServerConnection


__all__ = ["run_server"]

downloading_tasks: dict[str, BaseDownloader] = {}
server: asyncio.Future | None = None
client_connected: bool = False


async def send(ws: ServerConnection, event: str, **data: ty.Any) -> None:
    data.update({"event": event})
    with suppress(ConnectionClosed):
        await ws.send(orjson.dumps(data))


class ServerDPH(BaseDownloadingProgressHandler):
    def __init__(self, ws: ServerConnection, downloading_id: str):
        self.ws = ws
        self.downloading_id = downloading_id
        super().__init__()

    def init_status(self, status, total_count=None) -> None:
        super().init_status(status, total_count)
        asyncio.create_task(self._init_status())

    async def _init_status(self):
        await send(
            self.ws,
            "init_status",
            downloading_id=self.downloading_id,
            status=ty.cast(DownloadProcessStatus, self._status).value,
            total_count=self._total_count,
            done_count=self._done_count,
        )

    def progress(self, count: int) -> None:
        super().progress(count)
        asyncio.create_task(self._show_progress())

    async def _show_progress(self) -> None:
        await send(
            self.ws,
            "progress",
            downloading_id=self.downloading_id,
            done_count=self._done_count,
        )

    def show_progress(self) -> None:
        pass


async def download(ws: ServerConnection, sid: int, stype: SourceType) -> None:
    downloading_id = get_downloading_id(sid, stype)
    logger.info(f"downloading request: {downloading_id}")
    db = Database()
    if downloading_id in downloading_tasks:
        return await ty.cast(
            ServerDPH, downloading_tasks[downloading_id].process_handler
        )._init_status()
    try:
        assert (source := db.get_source_by_sid(sid, stype.value))
        assert (book := db.get_book_by_bid(source.related_book))
        assert (driver := BaseDriver.get_suitable_driver(source.url))
    except AssertionError:
        return
    downloader = downloading_tasks[downloading_id] = driver.downloader_factory(
        book.to_raw_book(source), ServerDPH(ws, downloading_id)
    )
    if await downloader.download_book():
        db.save(downloader)
        logger.info(f"downloading finished: {stype.name}-{sid}")
    del downloading_tasks[downloading_id]


async def terminate(downloading_id: str) -> None:
    logger.info(f"terminating request: {downloading_id}")
    if not (downloader := downloading_tasks.get(downloading_id)):
        return
    await downloader.terminate()
    logger.info(f"terminating finished: {downloading_id}")


async def handler(websocket: ServerConnection):
    logger.debug("Client connected")
    global client_connected
    client_connected = True
    for downloading_id in downloading_tasks:
        downloading_tasks[downloading_id].process_handler.ws = websocket  # type: ignore
        asyncio.create_task(
            ty.cast(
                ServerDPH, downloading_tasks[downloading_id].process_handler
            )._init_status()
        )

    try:
        async for message in websocket:
            try:
                data = orjson.loads(message)
                assert (command := data.get("command")) is not None
                if command == "download":
                    assert isinstance(sid := data.get("sid"), int)
                    assert (stype := data.get("stype")) in SourceType
                    asyncio.create_task(
                        download(websocket, sid, SourceType[stype])
                    )
                elif command == "terminate":
                    assert isinstance(sid := data.get("sid"), int)
                    assert (stype := data.get("stype")) in SourceType
                    asyncio.create_task(
                        terminate(get_downloading_id(sid, SourceType[stype]))
                    )
            except (orjson.JSONDecodeError, AssertionError):
                pass
            except Exception as e:
                logger.trace(e)
    except ConnectionClosedOK:
        pass
    except ConnectionClosedError:
        logger.error("Client closed with error. waiting for client")
        client_connected = False
        await asyncio.sleep(60)
        if client_connected:
            return
        logger.error("Client not connected. shutdowning")
    except Exception as e:
        logger.exception(e)

    client_connected = False
    await shutdown()


async def shutdown():
    logger.info("shutdowning")
    await asyncio.gather(
        *(terminate(downloading_id) for downloading_id in downloading_tasks)
    )
    server.cancel()  # type: ignore
    logger.info("Downloader server stopped\n\n")


async def run_server():
    global server
    server = asyncio.Future()
    threading.current_thread().name = "DownloaderServer"
    with suppress(asyncio.CancelledError):
        async with serve(handler, "localhost", 8765):
            logger.info("Downloader server started")
            await server

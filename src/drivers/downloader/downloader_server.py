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
from models.book import SourceId

from ..base_downloader import (
    BaseDownloader,
    BaseDownloadingProgressHandler,
    DownloadProcessStatus,
)
from ..base_driver import BaseDriver

if ty.TYPE_CHECKING:
    from websockets.asyncio.server import ServerConnection


__all__ = ["run_server"]

downloading_tasks: dict[SourceId, BaseDownloader] = {}
server: asyncio.Future | None = None
client_connected: bool = False


async def send(ws: ServerConnection, event: str, **data: ty.Any) -> None:
    data.update({"event": event})
    with suppress(ConnectionClosed):
        await ws.send(orjson.dumps(data))


class ServerDPH(BaseDownloadingProgressHandler):
    def __init__(self, ws: ServerConnection, sid: SourceId):
        self.ws = ws
        self.sid = sid
        super().__init__()

    def init_status(self, status, total_count=None) -> None:
        super().init_status(status, total_count)
        asyncio.create_task(self._init_status())

    async def _init_status(self):
        await send(
            self.ws,
            "init_status",
            sid=str(self.sid),
            status=ty.cast(DownloadProcessStatus, self.status).value,
            total_count=self.total_count,
            done_count=self.done_count,
        )

    def progress(self, count: int) -> None:
        super().progress(count)
        asyncio.create_task(self._show_progress())

    async def _show_progress(self) -> None:
        await send(
            self.ws,
            "progress",
            sid=str(self.sid),
            done_count=self.done_count,
        )

    def show_progress(self) -> None:
        pass


async def download(ws: ServerConnection, sid: SourceId) -> None:
    logger.info(f"downloading request: {sid}")
    db = Database()
    if sid in downloading_tasks:
        return await ty.cast(
            ServerDPH, downloading_tasks[sid].process_handler
        )._init_status()
    try:
        assert (source := db.get_source_by_sid(sid))
        assert (book := db.get_book_by_bid(source.related_book))
        assert (driver := BaseDriver.get_suitable_driver(source.url))
    except AssertionError:
        return
    downloader = downloading_tasks[sid] = driver.downloader_factory(
        book.to_raw_book(source), ServerDPH(ws, sid)
    )
    if await downloader.download_book():
        db.save(downloader)
        logger.info(f"downloading finished: {sid}")
    del downloading_tasks[sid]


async def terminate(sid: SourceId) -> None:
    logger.info(f"terminating request: {sid}")
    if not (downloader := downloading_tasks.get(sid)):
        return
    await downloader.terminate()
    logger.info(f"terminating finished: {sid}")


async def handler(websocket: ServerConnection):
    logger.debug("Client connected")
    global client_connected
    client_connected = True
    for sid in downloading_tasks:
        downloading_tasks[sid].process_handler.ws = websocket  # type: ignore
        asyncio.create_task(
            ty.cast(
                ServerDPH, downloading_tasks[sid].process_handler
            )._init_status()
        )

    try:
        async for message in websocket:
            try:
                data = orjson.loads(message)
                assert (command := data.get("command")) is not None
                if command == "download":
                    assert isinstance(sid_text := data.get("sid"), str) and (
                        sid := SourceId.from_str(sid_text)
                    )
                    asyncio.create_task(download(websocket, sid))
                elif command == "terminate":
                    assert isinstance(sid_text := data.get("sid"), str) and (
                        sid := SourceId.from_str(sid_text)
                    )
                    asyncio.create_task(terminate(sid))
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
    await asyncio.gather(*(terminate(sid) for sid in downloading_tasks))
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

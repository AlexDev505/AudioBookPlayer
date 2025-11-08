from __future__ import annotations

import asyncio
import threading
import typing as ty
from contextlib import suppress

import orjson
from database import Database
from loguru import logger
from websockets.asyncio.server import serve
from websockets.exceptions import (
    ConnectionClosed,
    ConnectionClosedError,
    ConnectionClosedOK,
)

from ..base import (
    BaseDownloader,
    BaseDownloadProcessHandler,
    DownloadProcessStatus,
    Driver,
)

if ty.TYPE_CHECKING:
    from websockets.asyncio.server import ServerConnection

__all__ = ["run_server"]

downloading_tasks: dict[int, BaseDownloader] = {}
server: asyncio.Future | None = None
client_connected: bool = False


async def send(ws: ServerConnection, event: str, **data: ty.Any) -> None:
    data.update({"event": event})
    with suppress(ConnectionClosed):
        await ws.send(orjson.dumps(data))


class ServerDPH(BaseDownloadProcessHandler):
    def __init__(self, ws: ServerConnection, bid: int):
        self.ws = ws
        self.bid = bid
        super().__init__()

    def init(self, total_size: int, status: DownloadProcessStatus) -> None:
        super().init(total_size, status)
        asyncio.create_task(self._init())

    async def _init(self):
        await send(
            self.ws,
            "init",
            bid=self.bid,
            status=self._status.value,
            total_size=self.total_size,
            done_size=self.done_size,
        )

    def progress(self, size: int) -> None:
        super().progress(size)
        asyncio.create_task(self._show_progress(size))

    async def _show_progress(self, size: int) -> None:
        await send(self.ws, "progress", bid=self.bid, size=size)

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
            self.ws, "set_status", bid=self.bid, status=self._status.value
        )


async def download(ws: ServerConnection, bid: int) -> None:
    logger.info(f"downloading request: {bid}")
    if bid in downloading_tasks:
        return await downloading_tasks[bid].process_handler._init()
    try:
        with Database() as db:
            assert (book := db.get_book_by_bid(bid))
        assert (driver := Driver.get_suitable_driver(book.url))
    except AssertionError:
        return
    downloader = downloading_tasks[bid] = driver.downloader_factory(
        book, ServerDPH(ws, bid)
    )
    if await downloader.download_book():
        with Database(autocommit=True) as db:
            db.save(downloader.book)
        logger.info(f"downloading finished: {bid}")
    del downloading_tasks[bid]


async def terminate(bid: int) -> None:
    logger.info(f"terminating request: {bid}")
    if not (downloader := downloading_tasks.get(bid)):
        return
    await downloader.terminate()
    logger.info(f"terminating finished: {bid}")


async def handler(websocket: ServerConnection):
    logger.debug("Client connected")
    global client_connected
    client_connected = True
    for bid in downloading_tasks:
        downloading_tasks[bid].process_handler.ws = websocket  # type: ignore
        asyncio.create_task(downloading_tasks[bid].process_handler._init())

    try:
        async for message in websocket:
            try:
                data = orjson.loads(message)
                assert (command := data.get("command")) is not None
                if command == "download":
                    assert isinstance(bid := data.get("bid"), int)
                    asyncio.create_task(download(websocket, bid))
                elif command == "terminate":
                    assert isinstance(bid := data.get("bid"), int)
                    asyncio.create_task(terminate(bid))
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
    await asyncio.gather(*(terminate(bid) for bid in downloading_tasks))
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

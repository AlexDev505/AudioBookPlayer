from __future__ import annotations

import threading
import typing as ty
from contextlib import suppress

import orjson
from loguru import logger
from websockets.exceptions import ConnectionClosedOK
from websockets.sync.client import connect

from models.book import SourceType

from ..base_downloader import (
    BaseDownloadingProgressHandler,
    DownloadProcessStatus,
)
from .utils import get_downloading_id

if ty.TYPE_CHECKING:
    from websockets.sync.client import ClientConnection

    from models.book import BookSource


class Client:
    def __init__(self):
        self.websocket: ClientConnection | None = None
        self.process_handlers: dict[str, BaseDownloadingProgressHandler] = {}
        self._t: threading.Thread | None = None

    def connect(self):
        logger.debug("Connecting")
        try:
            self.websocket = connect("ws://localhost:8765", open_timeout=60)
        except Exception as e:
            logger.error(f"Failed to connect to WebSocket server: {e}")
            self.connect()

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None

    def run(self):
        self._t = threading.Thread(target=self._run)
        self._t.start()

    def _run(self):
        threading.current_thread().name = "DownloaderClient"
        if not self.websocket:
            raise RuntimeError("WebSocket connection not established")
        try:
            for message in self.websocket:
                with suppress(orjson.JSONDecodeError):
                    data = orjson.loads(message)
                    event = data["event"]
                    process_handler = self.process_handlers[
                        data["downloading_id"]
                    ]
                    if event == "init_status":
                        process_handler.init_status(
                            DownloadProcessStatus(data["status"]),
                            data["total_size"],
                        )
                        process_handler.set_done_count(data["done_count"])
                    elif event == "progress":
                        process_handler.set_done_count(data["done_count"])
        except ConnectionClosedOK:
            logger.debug("Connection closed OK")
        except Exception as e:
            logger.exception(e)
            self.connect()
            self.run()

    def _send(self, command: str, **data: ty.Any):
        logger.debug(f"sending {command} command")
        if not self.websocket:
            raise RuntimeError("WebSocket connection not established")
        data.update({"command": command})
        self.websocket.send(orjson.dumps(data))

    def download(
        self,
        source: BookSource,
        process_handler: BaseDownloadingProgressHandler,
    ):
        downloading_id = get_downloading_id(
            sid := source.id, stype := SourceType(source.__class__)
        )
        self.process_handlers[downloading_id] = process_handler
        self._send("download", sid=sid, stype=stype.name)

    def terminate(self, sid: int, stype: SourceType) -> None:
        self._send("terminate", sid=sid, stype=stype.name)

    def shutdown(self) -> None:
        if self.websocket:
            logger.debug("shutdowning")
            self.websocket.close()

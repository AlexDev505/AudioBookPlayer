from __future__ import annotations

import threading
import typing as ty
from contextlib import suppress

import orjson
from loguru import logger
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK
from websockets.sync.client import connect

from ..base import BaseDownloadProcessHandler, DownloadProcessStatus

if ty.TYPE_CHECKING:
    from websockets.sync.client import ClientConnection


class Client:
    def __init__(self):
        self.websocket: ClientConnection | None = None
        self.process_handlers: dict[int, BaseDownloadProcessHandler] = {}
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
                with suppress(orjson.JSONDecodeError, KeyError):
                    data = orjson.loads(message)
                    event = data["event"]
                    process_handler = self.process_handlers[data["bid"]]
                    if event == "init":
                        process_handler.init(
                            data["total_size"],
                            DownloadProcessStatus(data["status"]),
                        )
                        process_handler.done_size = data["done_size"]
                    elif event == "set_status":
                        process_handler.status = DownloadProcessStatus(
                            data["status"]
                        )
                    elif event == "progress":
                        with suppress(TypeError):
                            process_handler.progress(data["size"])
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

    def download(self, bid: int, process_handler: BaseDownloadProcessHandler):
        self.process_handlers[bid] = process_handler
        self._send("download", bid=bid)

    def terminate(self, bid: int) -> None:
        self._send("terminate", bid=bid)

    def shutdown(self) -> None:
        if self.websocket:
            logger.debug("shutdowning")
            self.websocket.close()

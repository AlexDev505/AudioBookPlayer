from __future__ import annotations

import threading
import typing as ty
from contextlib import suppress
from dataclasses import asdict
from pathlib import Path

import orjson
from websockets.sync.client import connect

from .base_downloader import BaseDownloadProcessHandler, DownloadProcessStatus

if ty.TYPE_CHECKING:
    from websockets.sync.client import ClientConnection

    from models.book import BookSource


class Client:
    def __init__(self):
        self.websocket: ClientConnection | None = None
        self.process_handlers: dict[int, BaseDownloadProcessHandler] = {}
        self._t: threading.Thread | None = None

    def connect(self):
        self.websocket = connect("ws://localhost:8765")

    @property
    def is_connected(self) -> bool:
        return self.websocket is not None

    def run(self):
        self._t = threading.Thread(target=self._run)
        self._t.start()

    def _run(self):
        if not self.websocket:
            raise RuntimeError("WebSocket connection not established")
        for message in self.websocket:
            with suppress(orjson.JSONDecodeError):
                data = orjson.loads(message)
                event = data["event"]
                process_handler = self.process_handlers[data["sid"]]
                if event == "init":
                    process_handler.init(
                        data["total_size"],
                        DownloadProcessStatus(data["status"]),
                    )
                elif event == "set_status":
                    process_handler.status = DownloadProcessStatus(
                        data["status"]
                    )
                elif event == "progress":
                    process_handler.progress(data["size"])

    def _send(self, command: str, **data: ty.Any):
        if not self.websocket:
            raise RuntimeError("WebSocket connection not established")
        data.update({"command": command})
        self.websocket.send(orjson.dumps(data))

    def download(
        self,
        source: BookSource,
        destination: Path,
        process_handler: BaseDownloadProcessHandler,
    ):
        self.process_handlers[source.id] = process_handler
        self._send(
            "download", source=asdict(source), destination=str(destination)
        )

    def terminate(self, sid: int) -> None:
        self._send("terminate", sid=sid)

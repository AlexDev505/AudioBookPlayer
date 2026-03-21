from __future__ import annotations

import threading
import typing as ty
from contextlib import suppress

import orjson
from loguru import logger
from websockets.exceptions import ConnectionClosedOK
from websockets.sync.client import connect

from models.book import SourceId

from ..base_downloader import (
    BaseDownloadingProgressHandler,
    DownloadProcessStatus,
)

if ty.TYPE_CHECKING:
    from websockets.sync.client import ClientConnection


class Client:
    def __init__(self):
        self.websocket: ClientConnection | None = None
        self.process_handlers: dict[str, BaseDownloadingProgressHandler] = {}
        self.queue: dict[SourceId, BaseDownloadingProgressHandler] = {}
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
                    process_handler = self.process_handlers[data["sid"]]
                    if event == "init_status":
                        process_handler.init_status(
                            DownloadProcessStatus(data["status"]),
                            data["total_size"],
                        )
                        process_handler.set_done_count(data["done_count"])
                        self._downloading_status_changed(
                            data["sid"], process_handler
                        )
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
        self, sid: SourceId, process_handler: BaseDownloadingProgressHandler
    ):
        if len(self.process_handlers) >= 5:
            self.queue[sid] = process_handler
            logger.opt(colors=True).debug(f"added to download queue: {sid}")
            return
        self.process_handlers[str(sid)] = process_handler
        self._send("download", sid=str(sid))

    def terminate(self, sid: SourceId) -> None:
        if sid in self.queue:
            del self.queue[sid]
        else:
            self._send("terminate", sid=str(sid))

    def shutdown(self) -> None:
        if self.websocket:
            logger.debug("shutdowning")
            self.websocket.close()

    def get_downloads(self) -> list[SourceId]:
        sids = [
            *ty.cast(
                ty.Iterable[SourceId],
                map(SourceId.from_str, self.process_handlers.keys()),
            ),
            *self.queue.keys(),
        ]
        for sid in sids:
            self._send("download", sid=str(sid))

        return sids

    def _downloading_status_changed(
        self, sid: str, dph: BaseDownloadingProgressHandler
    ) -> None:
        if dph.status in {
            DownloadProcessStatus.FINISHED,
            DownloadProcessStatus.TERMINATED,
        }:
            del self.process_handlers[sid]
            if self.queue:
                self.download(*self.queue.popitem())

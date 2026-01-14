from __future__ import annotations

import subprocess
import sys
import time
import typing as ty

from .base_downloader import (
    BaseDownloader,
    BaseDownloadProcessHandler,
    DownloadProcessStatus,
)
from .downloader_client import Client
from .downloader_server import run_server

if ty.TYPE_CHECKING:
    from models.book import Book, BookSource

    from .base_downloader import BaseDownloadProcessHandler

__all__ = [
    "run_server",
    "download",
    "BaseDownloader",
    "BaseDownloadProcessHandler",
    "DownloadProcessStatus",
]

client = Client()


def download(
    book: Book, source: BookSource, process_handler: BaseDownloadProcessHandler
):
    if not client.is_connected:
        run_client_server()
    client.download(source, book.dir_path / source.dir_path, process_handler)


def run_client_server():
    subprocess.Popen([sys.executable, "--run-downloader"])
    while not client.is_connected:
        try:
            client.connect()
        except Exception as e:
            print(f"Error connecting to downloader server: {e}")
        time.sleep(1)
    client.run()

import atexit
import os
import subprocess
import sys
import time

from models.book import SourceId

from ..base_downloader import BaseDownloadingProgressHandler
from .downloader_client import Client

client = Client()
_starting = False
_first = True


def download(sid: SourceId, process_handler: BaseDownloadingProgressHandler):
    if not client.is_connected:
        run_client_server()
    client.download(sid, process_handler)


def terminate(sid: SourceId):
    if not client.is_connected:
        run_client_server()
    client.terminate(sid)


def get_downloads() -> list[BaseDownloadingProgressHandler]:
    return client.get_downloads()


def shutdown():
    client.shutdown()


def run_client_server():
    if os.environ["PLATFORM"] != "Windows":
        # TODO
        raise NotImplementedError(
            "Downloader client server is not supported on non-Windows platforms"
        )
    global _starting, _first
    if _starting:
        while not client.is_connected:
            time.sleep(1)
        return
    _starting = True
    if _first:
        _first = False
        _run_server()
    while not client.is_connected:
        client.connect()
    client.run()
    _starting = False


def _run_server():
    cmd = [sys.executable, "--run-downloader"]
    if not getattr(sys, "frozen", False):
        cmd.insert(1, "run.py")
    subprocess.Popen(cmd)


atexit.register(shutdown)

import atexit
import os
import subprocess
import sys
import time

from models.book import BookSource, SourceType

from ..base_downloader import BaseDownloadingProgressHandler
from .downloader_client import Client

if getattr(sys, "frozen", False):
    FROZEN = True
    ROOT_DIR = getattr(sys, "_MEIPASS")
else:
    FROZEN = False
    ROOT_DIR = os.path.dirname(__file__)

os.environ["FFMPEG_PATH"] = f'"{os.path.join(ROOT_DIR, r"bin\ffmpeg.exe")}"'

client = Client()
_starting = False
_first = True


def download(
    source: BookSource, process_handler: BaseDownloadingProgressHandler
):
    if not client.is_connected:
        run_client_server()
    client.download(source, process_handler)


def terminate(sid: int, stype: SourceType):
    if not client.is_connected:
        run_client_server()
    client.terminate(sid, stype)


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
        _run_server()
        _first = False
    while not client.is_connected:
        client.connect()
    client.run()
    _starting = False


def _run_server():
    cmd = [sys.executable, "--run-downloader"]
    if not FROZEN:
        cmd.insert(1, "run.py")
    subprocess.Popen(cmd)


atexit.register(shutdown)

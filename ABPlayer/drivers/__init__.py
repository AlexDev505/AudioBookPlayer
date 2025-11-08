import atexit
import os
import subprocess
import sys
import time

from .akniga import AKniga
from .base import BaseDownloadProcessHandler, DownloadProcessStatus, Driver
from .bookmate import Bookmate
from .downloader.downloader_client import Client
from .downloader.downloader_server import run_server
from .izibuk import Izibuk
from .knigavuhe import KnigaVUhe
from .librivox import LibriVox
from .yakniga import Yakniga

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


def download(bid: int, process_handler: BaseDownloadProcessHandler):
    if not client.is_connected:
        run_client_server()
    client.download(bid, process_handler)


def terminate(bid: int):
    if not client.is_connected:
        run_client_server()
    client.terminate(bid)


def shutdown():
    client.shutdown()


def run_client_server():
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

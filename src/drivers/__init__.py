import os
import sys

from . import drivers
from .base_downloader import (
    BaseDownloadingProgressHandler,
    DownloadProcessStatus,
)
from .base_driver import BaseDriver
from .downloader import download, get_downloads, terminate

if getattr(sys, "frozen", False):
    ROOT_DIR = getattr(sys, "_MEIPASS")
else:
    ROOT_DIR = os.path.dirname(__file__)

os.environ["FFMPEG_PATH"] = f'"{os.path.join(ROOT_DIR, r"bin\ffmpeg")}"'

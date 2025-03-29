import os
import sys

from .akniga import AKniga
from .base import Driver, DownloadProcessStatus, BaseDownloadProcessHandler
from .izibuk import Izibuk
from .knigavuhe import KnigaVUhe
from .librivox import LibriVox


if getattr(sys, "frozen", False):
    ROOT_DIR = getattr(sys, "_MEIPASS")
else:
    ROOT_DIR = os.path.dirname(__file__)

os.environ["FFMPEG_PATH"] = f'"{os.path.join(ROOT_DIR, r"bin\ffmpeg.exe")}"'

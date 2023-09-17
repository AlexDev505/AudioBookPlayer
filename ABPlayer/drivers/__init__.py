import os

from .akniga import AKnigaDriver
from .base import Driver, DownloadProcessStatus, BaseDownloadProcessHandler
from .knigavuhe import KnigaVUhe


os.environ["FFPROBE_PATH"] = os.path.abspath(r"drivers\bin\ffprobe.exe")

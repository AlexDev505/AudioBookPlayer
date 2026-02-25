import os

from . import library as library
from . import search as search
from . import settings as settings
from .js_api import JSApi

if os.environ["PLATFORM"] == "Windows":
    from . import window_controls as window_controls

__all__ = ["JSApi"]

import os

from . import settings as settings
from .js_api import JSApi

if os.name == "nt":
    from . import window_controls as window_controls

__all__ = ["JSApi"]

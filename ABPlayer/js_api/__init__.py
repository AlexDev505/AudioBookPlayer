import os

from .js_api import JSApi

if os.name == "nt":
    from . import window_controls

    JSApi.sections.append(window_controls.WindowControlsApi)

__all__ = ["JSApi"]

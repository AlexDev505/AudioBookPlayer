from __future__ import annotations

import typing as ty
from inspect import ismethod

import webview


class JSApi:
    sections: list[ty.Type[JSApi]] = []

    def init(self):
        window = self._window
        for section in self.sections:
            section = section()
            for name in dir(section):
                if not name.startswith("_"):
                    if ismethod(func := section.__getattribute__(name)):
                        window.expose(func)

    @property
    def _window(self) -> webview.Window:
        return webview.windows[0]

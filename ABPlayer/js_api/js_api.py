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

    @staticmethod
    def make_answer(data: ty.Any = ()) -> dict:
        return dict(status="ok", data=data)

    @staticmethod
    def error(exception: JSApiError) -> dict:
        return dict(status="fail", **exception.as_dict())


class JSApiError(Exception):
    code: int
    message: str
    extra: dict = {}

    def __init__(self, **kwargs):
        self.extra.update(kwargs)
        super().__init__(
            f"[{self.code}] {self.message} {self.extra if self.extra else ''}"
        )

    def as_dict(self) -> dict:
        return dict(code=self.code, message=self.message, extra=self.extra)

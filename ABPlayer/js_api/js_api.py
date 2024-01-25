from __future__ import annotations

import typing as ty
from functools import partial
from inspect import isfunction, ismethod

import webview
from loguru import logger

from tools import pretty_view


class JSApi:
    sections: list[ty.Type[JSApi]] = []

    def init(self):
        """
        Регистрирует методы для дальнейшего вызова из среды JS.
        """
        window = self._window
        for section in self.sections:
            section = section()
            for name in dir(section):
                if not name.startswith("_"):
                    func = section.__getattribute__(name)
                    if (ismethod(func) or isfunction(func)) and name not in dir(JSApi):
                        window.expose(func)

    @property
    def _window(self) -> webview.Window:
        return webview.windows[0]

    def evaluate_js(self, command: str) -> ty.Any:
        return self._window.evaluate_js(command)

    @staticmethod
    def make_answer(data: ty.Any = ()) -> dict:
        answer = dict(status="ok", data=data)
        logger.opt(lazy=True, depth=1).trace(
            "answer: {data}", data=partial(pretty_view, answer, multiline=True)
        )
        return answer

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
        logger.error(f"{self.__class__.__name__}: {self}")

    def as_dict(self) -> dict:
        return dict(code=self.code, message=self.message, extra=self.extra)

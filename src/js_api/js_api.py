from __future__ import annotations

import os
import typing as ty
from functools import partial, wraps
from inspect import isfunction, ismethod

import webview
from loguru import logger

from tools import pretty_view

from .exceptions import JSApiError


class JSApi:
    sections: list[JSApi] = []
    window: webview.Window

    def __init_subclass__(cls) -> None:
        JSApi.sections.append(cls())

    def init(self, window: webview.Window):
        """
        Registers methods for further invocation from the JS environment.
        """
        JSApi.window = window
        for section in self.sections:
            for name in dir(section):
                if not name.startswith("_"):
                    func = section.__getattribute__(name)
                    if (ismethod(func) or isfunction(func)) and name not in dir(
                        JSApi
                    ):
                        window.expose(self._catch_error(func))

    @property
    def _window(self) -> webview.Window:
        return JSApi.window

    def evaluate_js(self, command: str) -> ty.Any:
        return self._window.evaluate_js(command)

    @staticmethod
    def make_answer(data: ty.Any = ()) -> dict:
        answer = dict(status="ok", data=data)
        logger.opt(lazy=True, depth=1).trace(
            "answer: {data}",
            data=partial(
                pretty_view,
                answer,
                multiline=not os.getenv("NO_MULTILINE", False),
            ),
        )
        return answer

    @staticmethod
    def error(exception: JSApiError) -> dict:
        return dict(status="fail", **exception.as_dict())

    def _catch_error(self, func):
        @wraps(func)
        def _wrapper(*args, **kwargs):
            try:
                logger.opt(colors=True, lazy=True).debug(
                    "request: <r>{func}</r>{args}",
                    func=lambda: func.__name__,
                    args=lambda: (
                        " | "
                        + " | ".join(
                            f"<y>{arg}</y>" for arg in (*args, *kwargs.values())
                        )
                        if args or kwargs
                        else ""
                    ),
                )
                return self.make_answer(func(*args, **kwargs))
            except Exception as e:
                if not isinstance(e, JSApiError):
                    logger.exception(e)
                    e = JSApiError(
                        msg=_("unexpected_error"),
                        explain="Unexpected error",
                        base_exc=e,
                    )
                logger.error(str(e))
                return self.error(e)

        return _wrapper

    def __getattribute__(self, name: str, /) -> ty.Any:
        if name in dir(type(self)):
            return super().__getattribute__(name)
        if type(self) is JSApi:
            for section in self.sections:
                if name in dir(type(section)):
                    return getattr(section, name)
        return super().__getattribute__(name)

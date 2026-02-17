from __future__ import annotations

import asyncio
import typing as ty
from dataclasses import dataclass
from functools import partial

import aiohttp
import requests
from loguru import logger

from database import Database
from drivers.base_driver import (
    BaseDriver,
    DriverNotAuthenticated,
    LicensedDriver,
)
from tools import pretty_view

from .exceptions import (
    ConnectionFailedError,
    NoSuitableDriver,
    NotAuthenticated,
)
from .js_api import JSApi

if ty.TYPE_CHECKING:
    from models.book import BookPreview, RawBook


class LibraryApi(JSApi): ...

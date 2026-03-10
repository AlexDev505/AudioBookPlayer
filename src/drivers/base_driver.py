from __future__ import annotations

import os
import ssl
import types as tys
import typing as ty
from abc import ABC, abstractmethod
from asyncio.exceptions import CancelledError
from contextlib import suppress
from functools import wraps

import aiohttp
import certifi

from models.book import BookSource

from .base_downloader import BaseDownloader
from .tools import NotImplementedVariable, get_base_generics

if ty.TYPE_CHECKING:
    from models.book import BookPreview, RawBook

    class SessionRequired[**P, R](ty.Protocol):
        async def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R: ...


class BaseDriver[SourceT: BookSource](ABC):
    drivers: list[ty.Type[BaseDriver]] = []
    """ All available drivers """

    site_url: str = NotImplementedVariable()  # type: ignore
    """ Domain URL of the site where the driver is used """

    downloader_factory: ty.Type[BaseDownloader[SourceT]] = (
        NotImplementedVariable()
    )  # type: ignore

    session_factory: ty.Callable[[], aiohttp.ClientSession] = (
        aiohttp.ClientSession
    )
    request_kwargs: ty.Dict[str, ty.Any] = dict(
        ssl=ssl.create_default_context(cafile=certifi.where())
    )
    """ kwargs passed to every request made by the driver """
    __session: aiohttp.ClientSession | None = None

    def __init_subclass__(cls, **__):
        if ABC not in cls.__bases__:
            base_downloader_source_t = ty.get_args(
                tys.get_original_bases(BaseDownloader)[1]
            )[0]
            if (
                get_base_generics(cls, BaseDriver)[SourceT]
                != get_base_generics(cls.downloader_factory, BaseDownloader)[
                    base_downloader_source_t
                ]
            ):
                raise TypeError(
                    f"Driver `{cls.__name__}` must have the same source type "
                    "as its downloader factory"
                )
            cls.get_book = cls._ensure_session(cls.get_book)
            cls.get_book_series = cls._ensure_session(cls.get_book_series)
            cls.search_books = cls._ensure_session(cls.search_books)
            BaseDriver.drivers.append(cls)

    @classmethod
    def get_suitable_driver(cls, url: str) -> ty.Type[BaseDriver] | None:
        return next(
            filter(lambda driver: url.startswith(driver.site_url), cls.drivers),
            None,
        )

    @abstractmethod
    async def get_book(self, url: str) -> RawBook[SourceT]:
        """
        Method that retrieves full information about a book
        Must be implemented for each driver separately
        :param url: URL of the book
        :returns: Instance of the `Book`
        """

    @abstractmethod
    async def get_book_series(self, url: str) -> list[BookPreview]:
        """
        Method that retrieves preview information about books in a series
        Must be implemented for each driver separately
        :param url: URL of the book
        :returns: List of book previews
        """

    @abstractmethod
    async def search_books(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> list[BookPreview]:
        """
        Method that performs a search for books by query
        Must be implemented for each driver separately
        :param query: Search query
        :param limit: Number of books to return
        :param offset: Number of books to skip from the start
        :returns: List of book previews
        """

    @property
    def _session(self) -> aiohttp.ClientSession:
        if self.__session is None:
            self.__session = self.session_factory()
        return self.__session

    @staticmethod
    def _ensure_session[**P, R](
        func: SessionRequired[P, R],
    ) -> SessionRequired[P, R]:
        @wraps(func)
        async def _wrapper(self, *args: P.args, **kwargs: P.kwargs):
            await self._session.__aenter__()
            try:
                with suppress(CancelledError):
                    return await func(self, *args, **kwargs)
            finally:
                await self._session.__aexit__(None, None, None)
                self.__session = None

        return _wrapper

    def _request(self, method: str, url: str, **kwargs):
        kwargs = {**self.request_kwargs, **kwargs}
        return self._session.request(method, url, **kwargs)

    def get_page(self, url: str, **kwargs):
        return self._request("GET", url, **kwargs)

    def post(self, url: str, **kwargs):
        return self._request("POST", url, **kwargs)

    @classmethod
    @property
    def driver_name(cls) -> str:
        return cls.__name__

    def __hash__(self) -> int:
        return hash(self.driver_name)


class LicensedDriver(BaseDriver, ABC):
    AUTH_FILE: str
    is_authed: bool = False

    def __init_subclass__(cls, **kwargs):
        cls.AUTH_FILE = os.path.join(
            os.environ["AUTH_DIR"], f"{cls.driver_name}.dat"
        )
        super().__init_subclass__(**kwargs)

    @classmethod
    def auth(cls) -> bool:
        if not cls._auth():
            return False
        cls.is_authed = True
        return True

    @classmethod
    def auth_from_storage(cls) -> bool:
        if not cls._load_auth():
            return False
        cls.is_authed = True
        return True

    @classmethod
    @abstractmethod
    def _load_auth(cls) -> bool: ...

    @classmethod
    @abstractmethod
    def _auth(cls) -> bool: ...

    @classmethod
    def logout(cls) -> None:
        cls.is_authed = False
        if os.path.exists(cls.AUTH_FILE):
            os.remove(cls.AUTH_FILE)


class DriverNotAuthenticated(Exception):
    pass

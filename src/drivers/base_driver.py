from __future__ import annotations

import os
import types as tys
import typing as ty
from abc import ABC, abstractmethod

import aiohttp
import requests

from models.book import BookSource

from .base_downloader import BaseDownloader
from .tools import NotImplementedVariable, get_base_generics

if ty.TYPE_CHECKING:
    from models.book import BookPreview, RawBook


class BaseDriver[SourceT: BookSource](ABC):
    drivers: list[ty.Type[BaseDriver]] = []
    """ All available drivers """

    site_url: str = NotImplementedVariable()  # type: ignore
    """ Domain URL of the site where the driver is used """

    downloader_factory: ty.Type[BaseDownloader[SourceT]] = (
        NotImplementedVariable()
    )  # type: ignore

    session_factory: ty.Callable[[], requests.Session] = requests.Session
    async_session_factory: ty.Callable[[], aiohttp.ClientSession] = (
        aiohttp.ClientSession
    )
    __session: requests.Session | None = None

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
            BaseDriver.drivers.append(cls)

    @classmethod
    def get_suitable_driver(cls, url: str) -> ty.Type[BaseDriver] | None:
        return next(
            filter(lambda driver: url.startswith(driver.site_url), cls.drivers),
            None,
        )

    def get_page(self, url: str) -> requests.Response:
        """
        :param url: URL of the book
        :returns: Result of the GET request
        """
        return self._session.get(url)

    @property
    def _session(self) -> requests.Session:
        if self.__class__.__session is None:
            self.__class__.__session = self.session_factory()
        return self.__class__.__session

    @classmethod
    def close_session(cls):
        if cls.__session is not None:
            cls.__session.close()
            cls.__session = None

    @abstractmethod
    def get_book(self, url: str) -> RawBook[SourceT]:
        """
        Method that retrieves full information about a book
        Must be implemented for each driver separately
        :param url: URL of the book
        :returns: Instance of the `Book`
        """

    @abstractmethod
    def get_book_series(self, url: str) -> list[BookPreview]:
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

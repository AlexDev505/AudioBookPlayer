from __future__ import annotations

import typing as ty
from abc import ABC, abstractmethod

from selenium import webdriver

from .chromedriver import HiddenChromeWebDriver

if ty.TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver


class Driver(ABC):
    drivers: list[ty.Type[Driver]] = []  # Все доступные драйверы
    _browser: RemoteWebDriver | None = None
    _browser_connections: list[int] = []

    def __init__(self, use_shared_browser: bool = False):
        self._browser: RemoteWebDriver | None = None
        self.use_shared_browser = use_shared_browser

    def __init_subclass__(cls, **kwargs):
        Driver.drivers.append(cls)

    def __enter__(self) -> Driver:
        self.get_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.quit_browser()

    def _get_shared_browser(self) -> RemoteWebDriver:
        self.__class__._browser_connections.append(id(self))
        if self.__class__.__base__._browser is None:
            self.__class__.__base__._browser = self.__class__._get_driver()(
                options=self.__class__._get_driver_options()
            )
        return self.__class__.__base__._browser

    def _quit_shared_browser(self) -> None:
        if self.__class__.__base__._browser is not None:
            self.__class__.__base__._browser.quit()
            self.__class__.__base__._browser = None

    def get_browser(self) -> RemoteWebDriver:
        """
        :returns: Драйвер, для работы с браузером.
        """
        if self.use_shared_browser:
            return self._get_shared_browser()

        if self._browser is None:
            self._browser = self._get_driver()(options=self._get_driver_options())
        return self._browser

    def quit_browser(self) -> None:
        if self.use_shared_browser:
            self._quit_shared_browser()
        else:
            if self._browser is not None:
                self._browser.quit()
                self._browser = None

    def get_page(self, url: str) -> webdriver.Chrome:
        """
        :param url: Ссылка на книгу.
        :returns: Загруженную в драйвер страницу.
        """
        driver = self.get_browser()
        driver.get(url)
        return driver

    @abstractmethod
    def get_book(self, url: str) -> dict:
        """
        Метод, получающий информацию о книге.
        Должен быть реализован для каждого драйвера отдельно.
        :param url: Ссылка на книгу.
        :returns: Инстанс книги.
        """

    @classmethod
    def _get_driver(cls) -> ty.Type[RemoteWebDriver]:
        """
        :returns: Нужный драйвер браузера.
        """
        return HiddenChromeWebDriver

    @classmethod
    def _get_driver_options(cls) -> webdriver.ChromeOptions:
        """
        :returns: Настройки драйвера браузера.
        """
        options = webdriver.ChromeOptions()
        options.add_argument("headless")
        options.add_argument("disable-gpu")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        return options

    @classmethod
    @property
    @abstractmethod
    def site_url(cls) -> str:
        """
        :returns: Ссылка на сайт, с которым работает браузер.
        """

    @classmethod
    @property
    def driver_name(cls) -> str:
        return cls.__name__

    def __del__(self):
        if self.use_shared_browser:
            if id(self) in self.__class__._browser_connections:
                self.__class__._browser_connections.remove(id(self))
            if not self.__class__._browser_connections:
                self.quit_browser()
        else:
            self.quit_browser()

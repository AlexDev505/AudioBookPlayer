from __future__ import annotations

import typing as ty
from abc import ABC, abstractmethod

if ty.TYPE_CHECKING:
    from selenium import webdriver

    from database import Book


class Driver(ABC):
    def get_driver(self):
        """
        :returns: Driver for working with the browser.
        """
        return self.driver(
            executable_path=self.driver_path, options=self.driver_options
        )

    def get_page(self, url: str):
        """
        :param url: URL of the book.
        :returns: Page loaded in the driver.
        """
        driver = self.get_driver()
        driver.get(url)
        return driver

    @abstractmethod
    def get_book(self, url: str) -> Book:
        """
        Method to get information about the book.
        Must be implemented separately for each driver.
        :param url: URL of the book.
        :returns: Book instance.
        """

    @property
    @abstractmethod
    def driver(self) -> ty.Union[ty.Type[webdriver.Chrome], ty.Type[webdriver.Firefox]]:
        """
        :returns: Browser driver.
        """

    @property
    @abstractmethod
    def driver_path(self) -> str:
        """
        :returns: Path to the browser driver.
        """

    @property
    @abstractmethod
    def driver_options(
        self,
    ) -> ty.Union[webdriver.ChromeOptions, webdriver.FirefoxOptions]:
        """
        :returns: Browser driver settings.
        """

    @property
    @abstractmethod
    def site_url(self):
        """
        :returns: URL of the website the browser is working with.
        """

    @property
    def driver_name(self):
        return self.__class__.__name__

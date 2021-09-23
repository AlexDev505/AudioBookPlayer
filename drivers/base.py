from __future__ import annotations

import typing as ty
from abc import ABC, abstractmethod

if ty.TYPE_CHECKING:
    from selenium import webdriver

    from database import Book


class Driver(ABC):
    def get_driver(self):
        """
        :returns: Драйвер, для работы с браузером.
        """
        return self.driver(
            executable_path=self.driver_path, options=self.driver_options
        )

    def get_page(self, url: str):
        """
        :param url: Ссылка на книгу.
        :returns: Загруженную в драйвер страницу.
        """
        driver = self.get_driver()
        driver.get(url)
        return driver

    @abstractmethod
    def get_book(self, url: str) -> Book:
        """
        Метод, получающий информацию о книге.
        Должен быть реализован для каждого драйвера отдельно.
        :param url: Ссылка на книгу.
        :returns: Инстанс книги.
        """

    @property
    @abstractmethod
    def driver(self) -> ty.Union[ty.Type[webdriver.Chrome], ty.Type[webdriver.Firefox]]:
        """
        :returns: Нужный драйвер браузера.
        """

    @property
    @abstractmethod
    def driver_path(self) -> str:
        """
        :returns: Путь к драйверу браузера.
        """

    @property
    @abstractmethod
    def driver_options(
        self,
    ) -> ty.Union[webdriver.ChromeOptions, webdriver.FirefoxOptions]:
        """
        :returns: Настройки драйвера браузера.
        """

    @property
    @abstractmethod
    def site_url(self):
        """
        :returns: Ссылка на сайт, с которым работает браузер.
        """

    @property
    def driver_name(self):
        return self.__class__.__name__

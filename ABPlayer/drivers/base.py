from __future__ import annotations

import os
import sys
import typing as ty
from abc import ABC, abstractmethod
from pathlib import Path

import eyed3
import requests
from loguru import logger
from selenium import webdriver

from .chromedriver import HiddenChromeWebDriver

if ty.TYPE_CHECKING:
    from database.tables.books import Book, BookItem
    from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver


def prepare_file_metadata(
    file_path: ty.Union[str, Path],
    book: Book,
    item_index: int,
    item: BookItem = None,
) -> None:
    """
    Изменяет метаданные аудио файла.
    :param file_path: Путь к аудио файлу.
    :param book: Игстанс книги.
    :param item_index: Порядковый номер файла.
    :param item: Инстанс главы(optional)
    """
    file = eyed3.load(file_path)
    file.initTag()
    file.tag.title = item.title if item else f"{book.author} - {book.name}"
    file.tag.artist = book.author
    file.tag.track_num = item_index + 1
    file.tag.save()


class BaseDownloadProcessHandler:
    """
    Обработчик процесса скачивания.
    Визуализирует процесс скачивания книги в пользовательском интерфейсе.
    """

    def __init__(self):
        self.total_size: int = ...
        self.done_size: int = ...

    def init(self, total_size: int) -> None:
        self.total_size = total_size
        self.done_size = 0

    def progress(self, size: int) -> None:
        self.done_size += size
        self.show_progress()

    def show_progress(self) -> None:
        """
        Отображает прогресс.
        """
        sys.stdout.write(
            f"\r{self.done_size}/{self.total_size}\t"
            f"{round(self.done_size / (self.total_size / 100), 2)} %"
        )
        sys.stdout.flush()


class Driver(ABC):
    drivers: ty.List[ty.Type[Driver]] = []  # Все доступные драйверы
    _browser: RemoteWebDriver | None = None
    _browser_connections: list[int] = []

    def __init__(self, user_shared_browser: bool = False):
        logger.opt(colors=True).debug(
            f"Creating driver <e>{self.driver_name}</e> <y>{id(self)} "
            f"</y> user_shared_browser=<y>{user_shared_browser}</y>"
        )
        self._browser: RemoteWebDriver | None = None
        self.user_shared_browser = user_shared_browser

    def __init_subclass__(cls, **kwargs):
        Driver.drivers.append(cls)

    def __enter__(self) -> Driver:
        self.get_browser()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.quit_browser()

    def _get_shared_browser(self) -> RemoteWebDriver:
        logger.opt(colors=True).debug(
            f"Driver <e>{self.__class__.driver_name}</e> <y>{id(self)}</y> "
            f"getting shared browser"
        )
        self.__class__._browser_connections.append(id(self))
        if self.__class__.__base__._browser is None:
            self.__class__.__base__._browser = self.__class__._get_driver()(
                options=self.__class__._get_driver_options()
            )
            logger.opt(colors=True).debug(
                f"Drover <e>{self.__class__.driver_name}</e> <y>{id(self)}</y> "
                "created Shared browser"
            )
        return self.__class__.__base__._browser

    def _quit_shared_browser(self) -> None:
        if self.__class__.__base__._browser is not None:
            self.__class__.__base__._browser.quit()
            self.__class__.__base__._browser = None
            logger.opt(colors=True).debug(
                f"Driver <e>{self.driver_name}</e> <y>{id(self)}</y> "
                "closed Shared browser"
            )

    def get_browser(self) -> RemoteWebDriver:
        """
        :returns: Драйвер, для работы с браузером.
        """
        if self.user_shared_browser:
            return self._get_shared_browser()

        if self._browser is None:
            logger.opt(colors=True).debug(
                f"Driver <e>{self.driver_name}</e> <y>{id(self)}</y> "
                "created Local browser"
            )
            self._browser = self._get_driver()(options=self._get_driver_options())
        return self._browser

    def quit_browser(self) -> None:
        if self.user_shared_browser:
            self._quit_shared_browser()
        else:
            if self._browser is not None:
                self._browser.quit()
                self._browser = None
                logger.opt(colors=True).debug(
                    f"Driver <e>{self.driver_name}</e> <y>{id(self)}</y> "
                    "closed Local browser"
                )

    def get_page(self, url: str) -> webdriver.Chrome:
        """
        :param url: Ссылка на книгу.
        :returns: Загруженную в драйвер страницу.
        """
        driver = self.get_browser()
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

    @abstractmethod
    def get_book_series(self, url: str) -> ty.List[Book]:
        """
        Метод, получающий информацию о книгах из серии.
        Должен быть реализован для каждого драйвера отдельно.
        :param url: Ссылка на книгу.
        :returns: Список неполных инстансов книг.
        """

    def download_book(
        self,
        book: Book,
        process_handler: BaseDownloadProcessHandler = None,
    ) -> ty.List[Path]:
        """
        Метод, скачивающий аудио файлы книги.
        :param book: Экземпляр книги.
        :param process_handler: Обработчик процесса скачивания.
        :return: Список путей к файлам.
        """
        item: BookItem

        urls = []  # Ссылки на файлы
        merged = False  # Если True, то в 1-ом файле присутствует несколько глав
        total_size = 0  # Общий размер книги(в байтах)

        # Устанавливаем значение флага `merged` и определяем общий размер
        for item in book.items:
            if (url := item.file_url) not in urls:
                urls.append(url)
                if (
                    content_length := requests.get(url, stream=True).headers.get(
                        "content-length"
                    )
                ) is not None:
                    total_size += int(content_length)
            else:
                merged = True

        if process_handler:
            process_handler.init(total_size)

        logger.opt(colors=True).debug(f"Audio files merged: <y>{merged}</y>")
        logger.opt(colors=True, lazy=True).debug(
            f"Total size: <y>{total_size} bytes</y>"
        )

        files = []
        if merged:
            for i, url in enumerate(urls):
                file_path = Path(
                    os.path.join(
                        book.dir_path,
                        f"{str(i + 1).rjust(2, '0')}. {book.author} - {book.name}.mp3",
                    )
                )
                self._download_file(file_path, url, process_handler)
                files.append(file_path)
                prepare_file_metadata(file_path, book, i)
        else:
            for i, item in enumerate(book.items):
                file_path = Path(os.path.join(book.dir_path, item.title + ".mp3"))
                self._download_file(file_path, item.file_url, process_handler)
                files.append(file_path)
                prepare_file_metadata(file_path, book, i, item)

        return files

    def _download_file(
        self,
        file_path: Path,
        url: str,
        process_handler: BaseDownloadProcessHandler,
    ) -> None:
        """
        Метод, скачивающий аудио файл.
        :param file_path: Путь для сохранения.
        :param url: Ссылка на файл.
        :param process_handler: Обработчик процесса скачивания.
        """
        logger.opt(colors=True).debug(f"Download the file <y>{file_path}</y>({url})")
        if not file_path.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)

        # Храним файл в переменной, чтобы можно было закрыть его из другой части кода.
        # Иначе, при остановке скачивания, возникает ошибка.
        self._file = open(file_path, "wb")
        resp = requests.get(str(url), timeout=10, stream=True)
        logger.opt(colors=True).debug(
            f"File size: <y>{resp.headers.get('content-length')}</y>"
        )
        if resp.headers.get("content-length") is None:
            self._file.write(resp.content)
        else:
            for data in resp.iter_content(chunk_size=5120):
                if process_handler:
                    process_handler.progress(len(data))
                self._file.write(data)
                self._file.flush()
        self._file.close()

    # Работает на python 3.9
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
        logger.opt(colors=True).debug(
            f"Deleting driver <e>{self.driver_name}</e> <y>{id(self)}</y>"
        )
        if self.user_shared_browser:
            if id(self) in self.__class__._browser_connections:
                self.__class__._browser_connections.remove(id(self))
            if not self.__class__._browser_connections:
                self.quit_browser()
        else:
            self.quit_browser()

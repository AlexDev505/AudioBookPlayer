from __future__ import annotations

import os
import typing as ty
from abc import ABC, abstractmethod
from pathlib import Path

import eyed3
import requests
from selenium import webdriver

# Относится к супер фиче, описанной ниже
# from pydub import AudioSegment
# os.environ["PATH"] += os.pathsep + "drivers/ffmpeg/bin"

if ty.TYPE_CHECKING:
    from database import Book, BookItem


def prepare_file_metadata(file_path: str, book: Book, item: BookItem, item_index: int):
    file = eyed3.load(file_path)
    file.initTag()
    file.tag.title = item.title
    file.tag.artist = book.author
    file.tag.track_num = item_index + 1
    file.tag.save()


class DownloadProcessHandler:
    def __init__(self):
        self.total_size: int = ...
        self.done_size: int = ...

    def init(self, total_size: int):
        self.total_size = total_size
        self.done_size = 0

    def progress(self, size: int):
        self.done_size += size
        self.move_progress()

    def move_progress(self):
        pass


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

    @abstractmethod
    def get_book_series(self, url: str) -> ty.List[Book]:
        """
        Метод, получающий информацию о книгах из серии.
        Должен быть реализован для каждого драйвера отдельно.
        :param url: Ссылка на книгу.
        :returns: Список неполных инстансов книг.
        """

    def download_book(
        self, book: Book, progress_handler: DownloadProcessHandler = None
    ):
        item: BookItem

        urls = []
        total_size = 0
        for item in book.items:
            if (url := item.file_url) not in urls:
                urls.append(url)
                if (
                    content_length := requests.get(url, stream=True).headers.get(
                        "content-length"
                    )
                ) is not None:
                    total_size += int(content_length)

        if progress_handler:
            progress_handler.init(total_size)

        dir_path = os.path.join(os.environ["dir_with_books"], book.author, book.name)
        for i, url in enumerate(urls):
            file_path = Path(os.path.join(dir_path, f".{i + 1}"))
            if not file_path.exists():
                file_path.parent.mkdir(parents=True, exist_ok=True)

            with open(file_path, "wb") as file:
                resp = requests.get(str(url), stream=True)
                if resp.headers.get("content-length") is None:
                    file.write(resp.content)
                else:
                    for data in resp.iter_content(chunk_size=5120):
                        progress_handler.progress(len(data))
                        file.write(data)

        # Супер фича, которая жрет 1.5к озу, работает 100 миллионов лет, но работает.
        # Пусть побудет здесь, может быть я придумаю, что с этим делать...
        # Если коротко, эта штука разделяет аудио файл на главы.
        # for i, item in enumerate(book.items):
        #     file_path = os.path.join(
        #         dir_path, f"{book.author} - {book.name}. {item.title}.mp3"
        #     )
        #     if not item.end_time:
        #         os.rename(
        #             os.path.join(dir_path, f".{item.file_index}"),
        #             file_path,
        #         )
        #     else:
        #         chapter = AudioSegment.from_mp3(
        #             os.path.join(dir_path, f".{item.file_index}")
        #         )
        #         chapter = chapter[item.start_time * 1000 : (item.end_time - 1) * 1000]
        #         chapter.export(file_path)
        #
        #     prepare_file_metadata(file_path, book, item, i)

    @property
    def driver(self) -> ty.Union[ty.Type[webdriver.Chrome], ty.Type[webdriver.Firefox]]:
        """
        :returns: Нужный драйвер браузера.
        """
        return webdriver.Chrome

    @property
    def driver_path(self) -> str:
        """
        :returns: Путь к драйверу браузера.
        """
        return r"drivers\chromedriver"

    @property
    def driver_options(
        self,
    ) -> ty.Union[webdriver.ChromeOptions, webdriver.FirefoxOptions]:
        """
        :returns: Настройки драйвера браузера.
        """
        options = webdriver.ChromeOptions()
        options.add_argument("headless")
        options.add_argument("disable-gpu")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        return options

    @property
    @abstractmethod
    def site_url(self):
        """
        :returns: Ссылка на сайт, с которым работает браузер.
        """

    @property
    def driver_name(self):
        return self.__class__.__name__

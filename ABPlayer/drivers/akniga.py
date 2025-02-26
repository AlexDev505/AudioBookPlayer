import re
import time
import typing as ty
from abc import ABC, abstractmethod
from contextlib import suppress

import webview
from bs4 import BeautifulSoup
from loguru import logger

from models.book import Book, BookItem, BookItems
from .base import Driver
from .downloaders import M3U8Downloader
from .tools import safe_name


"""
On the AKniga website, book information is loaded dynamically via JavaScript.
Therefore, to get complete data about the book, we need a JavaScript runtime environment.
"""


class BaseJsApi(ABC):
    @abstractmethod
    def get_book_data(self, url: str) -> dict:
        """
        Method that returns dynamically loaded book data.
        {
            "author": <str>,
            "titleonly": <str>,  # book title in plain text
            "items": [{
                "file": <int>,  # file number
                "title": <str>,  # chapter title
                "time_from_start": <str>,  # start point
                "time_finish": <str>,  # end point
            }, ...],
            "m3u8": <str>,  # link to the m3u8 file
        }
        """


class PyWebViewJsApi(BaseJsApi):
    """
    JavaScript runtime environment using Pywebview.
    Creates a hidden window, loads the book page there, and retrieves data from it.
    """

    def __init__(self):
        self._window: webview.Window | None = None
        self._result = {}
        self._active = False

    def get_book_data(self, url: str) -> dict:
        self._window = webview.create_window("", url=url, hidden=True)
        # Executing `self._get_book_data` after the page loads
        self._window.events.loaded += self._get_book_data
        self._active = True
        if len(webview.windows) == 1:  # There are currently no running pywebview windows
            webview.start()
        else:
            while self._active:
                time.sleep(1)
        return self._result

    def _get_book_data(self) -> None:
        for i in range(5):
            self._result = self._window.evaluate_js(
                """
                function get_data() {
                    return {
                        "author": bookData[page_bid].author,
                        "titleonly": bookData[page_bid].titleonly,
                        "items": bookData[page_bid].items,
                        "m3u8": hls[page_bid].url
                    }
                }
                get_data()
                """
            )
            if self._result:
                break
            time.sleep(5)
        else:
            logger.error(
                f"getting book data failed. url={self._window.get_current_url}"
            )
            self._window.load_url(self._window.get_current_url())
            return

        self._window.destroy()
        self._active = False


class AKniga(Driver):
    site_url = "https://akniga.org"
    downloader_factory = M3U8Downloader

    def __init__(self, js_api: ty.Type[BaseJsApi] = PyWebViewJsApi):
        super().__init__()
        self.js_api = js_api

    def get_book(self, url: str) -> Book:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        book_data = self.js_api().get_book_data(url)

        author = book_data["author"]
        name = book_data["titleonly"]
        description = (
            soup.select_one("div.description__article-main")
            .text.replace(
                soup.select_one(
                    "div.description__article-main "
                    "> div.content__main__book--item--caption"
                ).text,
                "",
            )
            .strip()
        )

        try:
            series_name = soup.select_one(
                "span.caption__article-main--book:"
                "has(+ div.content__main__book--item--series-list) > a"
            ).text.strip()
        except AttributeError:
            series_name = ""
        try:
            number_in_series = (
                soup.select_one(
                    "div.content__main__book--item--series-list > a.current > b"
                )
                .text.strip()
                .strip(".")
            )
        except AttributeError:
            number_in_series = ""
        duration = " ".join(
            [obj.text for obj in soup.select("span[class*='book-duration-'] > span")]
        ).strip()
        reader = soup.select_one("a.link__reader span").text
        preview = soup.select_one("div.book--cover img").attrs["src"]
        items = BookItems()
        for item in book_data["items"]:
            items.append(
                BookItem(
                    file_url=book_data["m3u8"],
                    file_index=item["file"] - 1,
                    title=item["title"],
                    start_time=item["time_from_start"],
                    end_time=item["time_finish"],
                )
            )

        return Book(
            author=safe_name(author),
            name=safe_name(name),
            series_name=safe_name(series_name),
            number_in_series=number_in_series,
            description=description,
            reader=reader,
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=items,
        )

    def get_book_series(self, url: str) -> ty.List[Book]:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        series_element = soup.select_one(
            "span.caption__article-main--book:"
            "has(+ div.content__main__book--item--series-list) > a"
        )
        series_page_link = series_element.attrs["href"]
        series_name = series_element.text.strip()

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")
        soups = [soup]
        for el in soup.select("a.page__nav--standart"):
            page = self.get_page(el.attrs["href"])
            soups.append(BeautifulSoup(page.content, "html.parser"))

        books = []
        for soup in soups:
            for el in soup.select("div.content__main__articles--series-item"):
                url = el.select_one("a.content__article-main-link").attrs["href"]
                author = el.select_one(
                    "span.link__action--author"
                    r'> svg:has(use[xlink\:href="#author"]) ~ a'
                ).text.strip()
                try:
                    name = el.select_one("div.article--cover > a > img").attrs["alt"]
                except AttributeError:
                    name = (
                        el.select_one(".caption__article-main")
                        .text.replace(f"{author} - ", "")
                        .strip()
                    )
                reader = el.select_one(
                    "span.link__action--author"
                    r'> svg:has(use[xlink\:href="#performer"]) ~ a'
                ).text.strip()
                number_in_series = el.select_one(".number").text.strip()
                books.append(
                    Book(
                        name=safe_name(name),
                        url=url,
                        reader=safe_name(reader),
                        series_name=safe_name(series_name),
                        number_in_series=number_in_series,
                    )
                )

        return books

    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        books = []
        page_number = 1

        while True:
            if len(books) == limit:
                break

            url = self.site_url + f"/search/books/page{page_number}/?q={query}"

            page = self.get_page(url)
            soup = BeautifulSoup(page.text, "html.parser")

            elements = soup.select(
                "div.content__main__articles--item:not(:has(svg[class*='biblio']))"
            )
            if not elements:
                break

            if offset:
                if offset > len(elements):
                    offset -= len(elements)
                    elements.clear()
                else:
                    elements = elements[offset:]
                    offset = 0

            for el in elements:
                with suppress(AttributeError):
                    url = el.select_one("div.article--cover > a").attrs["href"]
                    preview = el.select_one("div.article--cover > a > img").attrs["src"]
                    author = el.select_one(
                        "span.link__action--author"
                        r'> svg:has(use[xlink\:href="#author"]) ~ a'
                    ).text.strip()
                    try:
                        name = el.select_one("div.article--cover > a > img").attrs[
                            "alt"
                        ]
                    except AttributeError:
                        name = (
                            el.select_one(".caption__article-main")
                            .text.replace(f"{author} - ", "")
                            .strip()
                        )
                    try:
                        reader = el.select_one(
                            "span.link__action--author"
                            r'> svg:has(use[xlink\:href="#performer"]) ~ a'
                        ).text.strip()
                    except AttributeError:
                        reader = "no data"
                    duration = el.select_one(
                        "span.link__action--label--time"
                    ).text.strip()
                    try:
                        series_name = el.select_one(
                            "span.link__action--author"
                            r'> svg:has(use[xlink\:href="#series"]) ~ a'
                        ).text.strip()
                        series_name = re.sub(r" \(\d+\)$", "", series_name)
                    except AttributeError:
                        series_name = ""
                    books.append(
                        Book(
                            author=safe_name(author),
                            name=safe_name(name),
                            series_name=safe_name(series_name),
                            reader=reader,
                            duration=duration,
                            url=url,
                            preview=preview,
                            driver=self.driver_name,
                        )
                    )
                    if len(books) == limit:
                        break

            page_number += 1

        return books


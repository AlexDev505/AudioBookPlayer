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
from .downloaders import MergedM3U8Downloader
from .tools import safe_name, find_in_soup


"""
On the AKniga website, book information is loaded dynamically via JavaScript.
Therefore, to get complete book data, we need a JavaScript execution environment.
"""


class BaseJsApi(ABC):
    @abstractmethod
    def get_book_data(self, url: str) -> dict:
        """
        Method that returns dynamically loaded book data.
        {
            "author": <str>,
            "titleonly": <str>,  # clean book title
            "items": [{
                "file": <int>,  # file number
                "title": <str>,  # chapter title
                "time_from_start": <str>,  # start time
                "time_finish": <str>,  # end time
            }, ...],
            "m3u8": <str>,  # link to m3u8 file
        }
        """


class PyWebViewJsApi(BaseJsApi):
    """
    JavaScript execution environment using Pywebview.
    Creates a hidden window, loads the book page there, and retrieves data from it.
    """

    def __init__(self):
        self._window: webview.Window | None = None
        self._result = {}
        self._active = False

    def get_book_data(self, url: str) -> dict:
        self._window = webview.create_window("", url=url, hidden=True)
        # Execute `self._get_book_data` after the page loads
        self._window.events.loaded += self._get_book_data
        self._active = True
        if (
            len(webview.windows) == 1
        ):  # Currently, there are no running pywebview windows
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
    downloader_factory = MergedM3U8Downloader

    def __init__(self, js_api: ty.Type[BaseJsApi] = PyWebViewJsApi):
        super().__init__()
        self.js_api = js_api

    def get_book(self, url: str) -> Book:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        book_data = self.js_api().get_book_data(url)

        author = book_data.get("author") or _("unknown_author")
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

        series_name = find_in_soup(
            soup,
            "span.caption__article-main--book:"
            "has(+ div.content__main__book--item--series-list) > a",
        )
        number_in_series = find_in_soup(
            soup, "div.content__main__book--item--series-list > a.current > b"
        ).strip(".")
        duration = " ".join(
            [obj.text for obj in soup.select("span[class*='book-duration-'] > span")]
        ).strip()
        reader = find_in_soup(soup, "a.link__reader span")
        preview = soup.select_one("div.book--cover img").attrs["src"]
        items = BookItems()
        for item in book_data["items"]:
            items.append(
                BookItem(
                    file_url=book_data["m3u8"],
                    file_index=item["file"] - 1,
                    title=safe_name(item["title"]),
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
            reader=safe_name(reader),
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=items,
        )

    def get_book_series(self, url: str) -> ty.List[Book]:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        if not (
            element := soup.select_one(
                "span.caption__article-main--book:"
                "has(+ div.content__main__book--item--series-list) > a"
            )
        ):  # book has no series
            return []
        series_page_link = element.attrs["href"]

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")
        pages_soups = [soup]
        for el in soup.select("a.page__nav--standart"):
            page = self.get_page(el.attrs["href"])
            pages_soups.append(BeautifulSoup(page.content, "html.parser"))

        books = []
        for page in pages_soups:
            for card in page.select(
                "div.content__main__articles--series-item"
                ":not(:has(.caption__article-preview))"
            ):
                if book := self._parse_book_card(card):
                    books.append(book)

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

            if not (
                elements := soup.select(
                    "div.content__main__articles--item:not(:has(.caption__article-preview))"
                )
            ):
                break

            if offset:
                if offset > len(elements):
                    offset -= len(elements)
                    elements.clear()
                else:
                    elements = elements[offset:]
                    offset = 0

            for card in elements:
                if book := self._parse_book_card(card):
                    books.append(book)
                if len(books) == limit:
                    break

            page_number += 1

        return books

    def _parse_book_card(self, card: BeautifulSoup) -> Book | None:
        with suppress(AttributeError, KeyError, TypeError):
            url = card.select_one("div.article--cover > a").attrs["href"]
            preview = card.select_one("div.article--cover > a > img").attrs["src"]
            author = find_in_soup(
                card,
                r'span.link__action--author> svg:has(use[xlink\:href="#author"]) ~ a',
                _("unknown_author"),
            )
            try:
                name = card.select_one("div.article--cover > a > img").attrs["alt"]
            except AttributeError:
                name = (
                    card.select_one(".caption__article-main")
                    .text.replace(f"{author} - ", "")
                    .strip()
                )
            reader = find_in_soup(
                card,
                "span.link__action--author> "
                r'svg:has(use[xlink\:href="#performer"]) ~ a',
            )
            duration = find_in_soup(card, "span.link__action--label--time")
            series_name = number_in_series = ""
            if series := find_in_soup(
                card,
                r'span.link__action--author> svg:has(use[xlink\:href="#series"]) ~ a',
            ):
                if match := re.fullmatch(r"(?P<name>.+?) \((?P<number>\d+)\)", series):
                    series_name = match.group("name")
                    number_in_series = match.group("number")
                else:
                    series_name = series
            return Book(
                author=safe_name(author),
                name=safe_name(name),
                series_name=safe_name(series_name),
                number_in_series=number_in_series,
                reader=safe_name(reader),
                duration=duration,
                url=url,
                preview=preview,
                driver=self.driver_name,
            )

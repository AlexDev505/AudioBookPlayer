import re
import time
import typing as ty
from abc import ABC, abstractmethod
from contextlib import suppress

import webview
from bs4 import BeautifulSoup, Tag
from loguru import logger

from models.book import AudioBook, BookPreview, Chapter, RawBook

from ..base_driver import BaseDriver
from ..downloaders import MergedM3U8Downloader
from ..tools import find_in_soup, safe_name

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


class AKniga(BaseDriver[AudioBook]):
    site_url = "https://akniga.org"
    downloader_factory = MergedM3U8Downloader

    PER_PAGE = 12

    def __init__(self, js_api: ty.Type[BaseJsApi] = PyWebViewJsApi):
        super().__init__()
        self.js_api = js_api

    def get_book(self, url):
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        book_data = self.js_api().get_book_data(url)

        author = book_data.get("author") or _("unknown_author")
        title = book_data["titleonly"]
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
            [
                obj.text
                for obj in soup.select("span[class*='book-duration-'] > span")
            ]
        ).strip()
        narrator = find_in_soup(soup, "a.link__reader span")
        cover = soup.select_one("div.book--cover img").attrs["src"]
        chapters: list[Chapter] = []
        for item in book_data["items"]:
            chapters.append(
                Chapter(
                    title=safe_name(item["title"]),
                    url=book_data["m3u8"],
                    file_index=item["file"] - 1,
                    start_time=item["time_from_start"],
                    end_time=item["time_finish"],
                )
            )

        return RawBook(
            title=safe_name(title),
            author=safe_name(author),
            series_name=safe_name(series_name),
            number_in_series=number_in_series,
            description=description,
            source=AudioBook(
                url=url,
                cover=cover,
                narrator=safe_name(narrator),
                duration=duration,
                chapters=chapters,
            ),
        )

    def get_book_series(self, url):
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        if not (
            element := soup.select_one(
                "span.caption__article-main--book:"
                "has(+ div.content__main__book--item--series-list) > a"
            )
        ):  # book has no series
            return list[BookPreview]()
        series_page_link = element.attrs["href"]

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")
        pages_soups = [soup]
        for el in soup.select("a.page__nav--standart"):
            page = self.get_page(el.attrs["href"])
            pages_soups.append(BeautifulSoup(page.content, "html.parser"))

        books: list[BookPreview] = []
        for page in pages_soups:
            for card in page.select(
                "div.content__main__articles--series-item"
                ":not(:has(.caption__article-preview))"
            ):
                if book := self._parse_book_card(card):
                    books.append(book)

        return books

    async def search_books(self, query, limit=10, offset=0):
        books: list[BookPreview] = []
        page_number = offset // self.PER_PAGE + 1
        offset %= self.PER_PAGE

        while len(books) < limit:
            url = self.site_url + f"/search/books/page{page_number}/?q={query}"

            async with self._async_session.get(url) as response:
                page = await response.text()
            soup = BeautifulSoup(page, "html.parser")

            if not (
                elements := soup.select(
                    "div.content__main__articles--item:not(:has(.caption__article-preview))"
                )
            ):
                break

            if offset:
                elements = elements[offset:]
                offset = 0

            for card in elements:
                if book := self._parse_book_card(card):
                    books.append(book)
                if len(books) == limit:
                    break

            page_number += 1

        return books

    def _parse_book_card(self, card: Tag) -> BookPreview | None:
        with suppress(AttributeError, KeyError, TypeError):
            url = card.select_one("div.article--cover > a").attrs["href"]
            cover = card.select_one("div.article--cover > a > img").attrs["src"]
            author = find_in_soup(
                card,
                r'span.link__action--author> svg:has(use[xlink\:href="#author"]) ~ a',
                _("unknown_author"),
            )
            try:
                title = card.select_one("div.article--cover > a > img").attrs[
                    "alt"
                ]
            except AttributeError:
                title = (
                    card.select_one(".caption__article-main")
                    .text.replace(f"{author} - ", "")
                    .strip()
                )
            narrator = find_in_soup(
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
                if match := re.fullmatch(
                    r"(?P<name>.+?) \((?P<number>\d+)\)", series
                ):
                    series_name = match.group("name")
                    number_in_series = match.group("number")
                else:
                    series_name = series
            return BookPreview(
                title=safe_name(title),
                author=safe_name(author),
                series_name=safe_name(series_name),
                number_in_series=number_in_series,
                description="",
                urls={url},
                cover=cover,
                narrators={safe_name(narrator)},
                publications=set(),
                durations=[duration],
            )

import os
import re
import sys
import time
import typing as ty
from abc import ABC, abstractmethod
from contextlib import suppress

import orjson
import requests
import webview
from bs4 import BeautifulSoup
from models.book import Book, BookItem, BookItems

from .base import Driver
from .downloaders import MergedM3U8Downloader
from .tools import find_in_soup, safe_name

if getattr(sys, "frozen", False):
    DRIVERS_DIR = os.path.join(getattr(sys, "_MEIPASS"))
else:
    DRIVERS_DIR = os.path.dirname(__file__)

DECRYPT_SCRIPT = os.path.join(DRIVERS_DIR, "bin/akniga_decrypt.js")


"""
On the AKniga website, book information is loaded dynamically via JavaScript.
Therefore, to get complete book data, we need a JavaScript execution environment.
"""


class BaseJsApi(ABC):
    @abstractmethod
    def decrypt_hres(self, hres: str) -> str:
        """Decrypts URL to audio file"""


class PyWebViewJsApi(BaseJsApi):
    """
    JavaScript execution environment using Pywebview
    Uses already running pywebview window to execute JavaScript
    """

    def decrypt_hres(self, hres: str) -> str:
        _window = webview.windows[0]
        with open(DECRYPT_SCRIPT, encoding="utf-8") as f:
            script = f.read()
        script += f"\n\nplh.getHres('{hres}')"
        return _window.evaluate_js(script)


class AKniga(Driver):
    site_url = "https://akniga.org"
    downloader_factory = MergedM3U8Downloader

    PER_PAGE = 12
    HEADERS = {
        "origin": site_url,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }
    TOKEN_URL = "https://akniga.org/ajax/player/token"
    BOOK_URL = "https://akniga.org/ajax/b/{bid}"

    def __init__(self, js_api: ty.Type[BaseJsApi] = PyWebViewJsApi):
        super().__init__()
        self.js_api = js_api

    def get_book(self, url: str) -> Book:
        session = requests.Session()
        page = session.get(url, headers=self.HEADERS)

        sk = re.search(r"LIVESTREET_SECURITY_KEY = '(.+?)'", page.text).group(1)
        bid = re.search(r'data-bid="(.+?)"', page.text).group(1)
        token = session.post(
            self.TOKEN_URL,
            headers=self.HEADERS,
            data={
                "security_ls_key": sk,
                "bid": bid,
                "ts": int(time.time() * 1000),
            },
        ).json()["token"]

        book_data = session.post(
            self.BOOK_URL.format(bid=bid),
            headers=self.HEADERS,
            data={
                "security_ls_key": sk,
                "bid": bid,
                "token": token,
                "hls": True,
            },
        ).json()
        m3u8 = self.js_api().decrypt_hres(book_data["hres"])

        soup = BeautifulSoup(page.content, "html.parser")

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
            [
                obj.text
                for obj in soup.select("span[class*='book-duration-'] > span")
            ]
        ).strip()
        reader = find_in_soup(soup, "a.link__reader span")
        preview = soup.select_one("div.book--cover img").attrs["src"]
        items = BookItems()
        for item in orjson.loads(book_data["items"]):
            items.append(
                BookItem(
                    file_url=m3u8,
                    file_index=0,
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

    def search_books(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> list[Book]:
        books = []
        page_number = offset // self.PER_PAGE + 1
        offset %= self.PER_PAGE

        while len(books) < limit:
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
            preview = card.select_one("div.article--cover > a img").attrs["src"]
            author = find_in_soup(
                card,
                "span.link__action--author> a[href*='author']",
                _("unknown_author"),
            )
            try:
                name = card.select_one("div.article--cover > a img").attrs[
                    "alt"
                ]
            except AttributeError:
                name = card.select_one(".caption__article-main").text
            name = name.replace(f"{author} – ", "").strip()
            reader = find_in_soup(
                card, "span.link__action--author> a[href*='performer']"
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

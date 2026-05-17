import asyncio
import os
import re
import sys
import time
import typing as ty
from abc import ABC, abstractmethod
from contextlib import suppress

import orjson
import webview
from bs4 import BeautifulSoup, Tag
from loguru import logger

from models.book import AudioBook, BookPreview, Chapter, RawBook

from ..base_driver import BaseDriver
from ..downloaders import MergedM3U8Downloader
from ..tools import find_in_soup, safe_name

if getattr(sys, "frozen", False):
    DRIVERS_DIR = os.path.join(getattr(sys, "_MEIPASS"), "drivers")
else:
    DRIVERS_DIR = os.path.dirname(__file__)

DECRYPT_SCRIPT = os.path.join(DRIVERS_DIR, "akniga_decrypt.js")

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


class AKniga(BaseDriver[AudioBook]):
    site_url = "https://akniga.org"
    downloader_factory = MergedM3U8Downloader

    PER_PAGE = 12
    HEADERS = {
        "origin": site_url,
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
    }
    TOKEN_URL = "https://akniga.org/ajax/player/token"
    BOOK_URL = "https://akniga.org/ajax/b/{bid}"

    request_kwargs = {
        "headers": HEADERS,
    }

    def __init__(self, js_api: ty.Type[BaseJsApi] = PyWebViewJsApi):
        super().__init__()
        self.js_api = js_api

    async def get_book(self, url):
        async with self.get_page(url) as resp:
            page = await resp.text()

        sk = re.search(r"LIVESTREET_SECURITY_KEY = '(.+?)'", page).group(1)
        bid = re.search(r'data-bid="(.+?)"', page).group(1)
        async with self.post(
            self.TOKEN_URL,
            data={
                "security_ls_key": sk,
                "bid": bid,
                "ts": int(time.time() * 1000),
            },
        ) as resp:
            token = (await resp.json())["token"]

        async with self.post(
            self.BOOK_URL.format(bid=bid),
            data={
                "security_ls_key": sk,
                "bid": bid,
                "token": token,
                "hls": True,
            },
        ) as resp:
            book_data = await resp.json()

        m3u8 = self.js_api().decrypt_hres(book_data["hres"])

        soup = BeautifulSoup(page, "html.parser")

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
        for item in orjson.loads(book_data["items"]):
            chapters.append(
                Chapter(
                    title=safe_name(item["title"]),
                    url=m3u8,
                    file_index=0,
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

    async def get_book_series(self, url):
        async with self.get_page(url) as resp:
            page = await resp.text()
        soup = BeautifulSoup(page, "html.parser")

        if not (
            element := soup.select_one(
                "span.caption__article-main--book:"
                "has(+ div.content__main__book--item--series-list) > a"
            )
        ):  # book has no series
            return list[BookPreview]()
        series_page_link = element.attrs["href"]

        async with self.get_page(series_page_link) as resp:
            page = await resp.text()
        soup = BeautifulSoup(page, "html.parser")
        pages_soups = [
            soup,
            *await asyncio.gather(
                *[
                    self.get_page(el.attrs["href"])
                    for el in soup.select("a.page__nav--standart")
                ]
            ),
        ]

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

            async with self.get_page(url) as response:
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
            cover = card.select_one("div.article--cover > a img").attrs["src"]
            author = find_in_soup(
                card,
                "span.link__action--author> a[href*='author']",
                _("unknown_author"),
            )
            try:
                title = card.select_one("div.article--cover > a img").attrs[
                    "alt"
                ]
            except AttributeError:
                title = card.select_one(".caption__article-main").text
            title = title.replace(f"{author} – ", "").strip()
            narrator = find_in_soup(
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
                durations={duration},
            )

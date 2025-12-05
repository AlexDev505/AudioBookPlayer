import re
from contextlib import suppress

from bs4 import BeautifulSoup
from loguru import logger
from models.book import Book, BookItem, BookItems
from orjson import orjson

from .base import Driver
from .downloaders import MP3Downloader
from .tools import find_in_soup, safe_name


class Izibuk(Driver):
    site_url = "https://izib.uk"
    downloader_factory = MP3Downloader

    def get_book(self, url: str) -> Book:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")
        page = page.text

        name = soup.select_one("span[itemprop='name']").text.strip()
        author = find_in_soup(
            soup, "span a[href^='/author']", _("unknown_author")
        )

        series_name = find_in_soup(soup, "a[href^='/serie']")
        number_in_series = find_in_soup(
            soup,
            "div:has(>div>a[href^='/serie']) div:has(>strong) span",
            modification=lambda x: x.strip().removesuffix("."),
        )

        description = find_in_soup(soup, "div[itemprop='description']")

        reader = find_in_soup(
            soup, "div:has(>div>span[itemprop='author']) a[href^='/reader']"
        )

        duration = find_in_soup(
            soup,
            "div:has(>div>span[itemprop='author']) > div:last-child",
            modification=lambda x: x.strip().removeprefix(
                "Время: "  # Do not translate
            ),
        )

        preview = soup.select_one("img").attrs["src"]

        match = re.search(r"var player = new XSPlayer\(((\s*.*?)+?)\);", page)
        player = orjson.loads(match.group(1))
        files_host = f"https://{player['mp3_url_prefix']}"
        items = BookItems()
        for i, item in enumerate(player["tracks"]):
            items.append(
                BookItem(
                    file_url=f"{files_host}/{item[4]}",
                    file_index=i,
                    title=safe_name(item[1]),
                    start_time=0,
                    end_time=item[2],
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

    def get_book_series(self, url: str) -> list[Book]:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")
        author = find_in_soup(soup, "a[href^='/author']", _("unknown_author"))

        if not (
            element := soup.select_one("a[href^='/serie']")
        ):  # book has no series
            return []
        series_page_link = element.attrs["href"]
        series_name = element.text.strip()

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")

        books = []
        for card in soup.select(
            "#books_list>div:not(:has(a[href^='/book']+span))"
        ):
            if book := self._parse_book_card(card, author, series_name):
                books.append(book)

        return books

    def search_books(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> list[Book]:
        books = []
        page_number = 1

        while True:
            if len(books) == limit:
                break

            url = f"{self.site_url}/search?q={query}&p={page_number}"

            page = self.get_page(url)
            soup = BeautifulSoup(page.content, "html.parser")
            if not soup.select_one("#books_list > div a[href^='/art']"):
                break
            elements = soup.select(
                "#books_list>div>div:not(:has(a[href^='/art']+span))"
            )

            if offset:
                if offset > len(elements):
                    offset -= len(elements)
                    elements.clear()
                else:
                    elements = elements[offset:]
                    offset = 0

            for card in elements:
                if book := self._parse_book_card(card, _("unknown_author"), ""):
                    books.append(book)
                if len(books) == limit:
                    break

            page_number += 1

        return books

    def _parse_book_card(
        self, card: BeautifulSoup, author: str, series_name: str
    ) -> Book | None:
        with suppress(AttributeError, KeyError, TypeError):
            number = find_in_soup(
                card,
                "div",
                modification=lambda x: (
                    ""
                    if not re.fullmatch(r"#\d+", x.strip())
                    else x.strip().removeprefix("#")
                ),
            )
            element = card.select_one("div>a[href^='/art']:not(:has(>img))")
            url = f"{self.site_url}{element.attrs['href']}"
            name = element.text.strip()
            preview = card.select_one("img").attrs["src"]
            author = find_in_soup(card, "a[href^='/author']", author)
            reader = find_in_soup(card, "a[href^='/reader']")
            series_name = find_in_soup(card, "a[href^='/serie']", series_name)
            return Book(
                author=safe_name(author),
                name=safe_name(name),
                series_name=safe_name(series_name),
                number_in_series=number,
                reader=safe_name(reader),
                url=url,
                preview=preview,
                driver=self.driver_name,
            )

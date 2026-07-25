import re
from contextlib import suppress

from bs4 import BeautifulSoup
from loguru import logger
from models.book import Book, BookItem, BookItems
from orjson import orjson

from .base import Driver
from .downloaders import MP3Downloader
from .tools import find_in_soup, safe_name


class Uknig(Driver):
    site_url = "https://uknig.com"
    downloader_factory = MP3Downloader

    def get_book(self, url: str) -> Book:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")
        page = page.text

        name = soup.select_one("h1[itemprop='name']").text.strip()
        author = find_in_soup(
            soup, "div a[href*='/authors']", _("unknown_author")
        )

        series_name = find_in_soup(soup, "a[href*='/serie']")
        number_in_series = find_in_soup(
            soup,
            "div:has(>a[href*='/serie'])",
            modification=lambda x: re.search(r"\(#(\d+)\)", x.strip()).group(1),
        )

        description = find_in_soup(soup, ".description")

        reader = find_in_soup(soup, "a[href*='/readers']")

        duration = find_in_soup(soup, ".book-duration > div")

        preview = soup.select_one("img").attrs["src"]

        match = re.search(r"createPlayer\(\"(.+?)\"\)", page)
        if not match:
            raise ValueError("Book is licensed")
        playlist_url = match.group(1)
        playlist = orjson.loads(self.get_page(playlist_url).text)
        items = BookItems()
        for i, item in enumerate(playlist):
            items.append(
                BookItem(
                    file_url=item["file"].split(" or ")[0],
                    file_index=i,
                    title=safe_name(item["title"]),
                    start_time=0,
                    end_time=0,
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
        author = find_in_soup(
            soup, "div a[href*='/authors']", _("unknown_author")
        )

        if not (
            element := soup.select_one("a[href*='/series']")
        ):  # book has no series
            return []
        series_page_link = element.attrs["href"]
        series_name = element.text.strip()

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")

        books = []
        for card in soup.select(".book-item"):
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

            url = f"{self.site_url}/?q={query}&p={page_number}"

            page = self.get_page(url)
            soup = BeautifulSoup(page.content, "html.parser")
            if not soup.select_one(".book-item"):
                break
            elements = soup.select(".book-item")

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
                ".number-in-series",
                modification=lambda x: (
                    x.strip().removeprefix("#")
                ),
            )
            element = card.select_one("div>a[href*='/books']:not(:has(img))")
            url = element.attrs['href']
            name = element.text.strip()
            preview = card.select_one("img").attrs["data-original"]
            author = find_in_soup(card, "a[href*='/authors']", author)
            reader = find_in_soup(card, "a[href*='/reader']")
            series_name = find_in_soup(card, "a[href*='/series']", series_name)
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

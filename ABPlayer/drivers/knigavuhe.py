import re
import typing as ty
from contextlib import suppress

from bs4 import BeautifulSoup
from orjson import orjson

from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name, find_in_soup


class KnigaVUhe(Driver):
    site_url = "https://knigavuhe.org"
    downloader_factory = MP3Downloader

    def get_book(self, url: str) -> Book:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")
        page = page.text

        match = re.search(r"cur\.book = (.+);", page)
        book = orjson.loads(match.group(1))

        match = re.search(r"var player = new BookPlayer\(\d+, (\[.+?]).+\);", page)
        playlist = orjson.loads(match.group(1))

        name = book["name"]
        author = find_in_soup(
            soup, "span.book_title_elem > span > a", _("unknown_author")
        )

        series_name = find_in_soup(soup, "div.book_serie_block_title > a")
        number_in_series = find_in_soup(
            soup,
            "div.book_serie_block_item > span:has(+ strong)",
            modification=lambda x: x.strip().strip("."),
        )

        description = find_in_soup(soup, "div.book_description")
        reader = find_in_soup(soup, "a[href^='/reader/']")
        duration = ""
        with suppress(AttributeError, TypeError):
            duration = (
                soup.find("span", string="Время звучания:").parent.contents[-1].strip()
            )  # Do not translate
        preview = soup.select_one("div.book_cover > img").attrs["src"]

        items = BookItems()
        for i, item in enumerate(playlist):
            items.append(
                BookItem(
                    file_url=item["url"],
                    file_index=i,
                    title=safe_name(item["title"]),
                    start_time=0,
                    end_time=item["duration"],
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
        author = find_in_soup(
            soup, "span.book_title_elem > span > a", _("unknown_author")
        )

        if not (el := soup.select_one("div.book_serie_block_title > a")):
            return []  # book has no series
        series_page_link = self.site_url + el.attrs["href"]
        series_name = el.text

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")

        books = []
        for card in soup.select("div.bookkitem:not(:has(.bookkitem_litres_icon))"):
            if book := self._parse_book_card(card, author, series_name):
                books.append(book)
                url = name = reader = ""
                for element in card.select("div.bookkitem_other_versions_list > a"):
                    if url == "":
                        url = self.site_url + element.attrs["href"]
                        name = element.text
                    elif reader == "":
                        reader = element.text
                        books.append(
                            Book(
                                author=safe_name(author),
                                name=safe_name(name),
                                series_name=safe_name(series_name),
                                number_in_series=book.number_in_series,
                                reader=safe_name(reader),
                                url=url,
                                preview=book.preview,
                                driver=self.driver_name,
                            )
                        )
                        url = name = reader = ""

        return books

    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        books = []
        page_number = 1

        while True:
            if len(books) == limit:
                break

            url = self.site_url + f"/search/?q={query}&page={page_number}"

            page = self.get_page(url)
            soup = BeautifulSoup(page.text, "html.parser")

            if not (
                elements := soup.select(
                    "div.bookkitem:not(:has(span.bookkitem_litres_icon))"
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
            url = card.select_one("a.bookkitem_cover").attrs["href"]
            preview = card.select_one("img.bookkitem_cover_img").attrs["src"]
            number_in_series = find_in_soup(
                card,
                "span.bookkitem_serie_index",
                modification=lambda x: x.strip("."),
            )
            name = find_in_soup(card, "a.bookkitem_name")
            if number_in_series:
                name = name.removeprefix(f"{number_in_series}. ")
            author = find_in_soup(card, "span.bookkitem_author > a", author)
            reader = find_in_soup(card, "a[href^='/reader/']")
            duration = find_in_soup(card, "span.bookkitem_meta_time")
            series_name = find_in_soup(card, "a[href^='/serie/']", series_name)
            return Book(
                author=safe_name(author),
                name=safe_name(name),
                series_name=safe_name(series_name),
                number_in_series=number_in_series,
                reader=safe_name(reader),
                duration=duration,
                url=self.site_url + url,
                preview=preview,
                driver=self.driver_name,
            )

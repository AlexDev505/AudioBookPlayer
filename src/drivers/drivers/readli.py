import re
from contextlib import suppress
from copy import copy

from bs4 import BeautifulSoup, Tag

from models.book import BookPreview, RawBook, TextBook

from ..base_driver import BaseDriver
from ..downloaders import ZipDownloader
from ..tools import find_in_soup, safe_name


class Readli(BaseDriver[TextBook]):
    site_url = "https://readli.net"
    downloader_factory = ZipDownloader

    SEARCH_URL = "https://readli.net/ajax-site/search-books-more/"
    SEARCH_PAYLOAD = {"offset": 0, "q": ""}

    @staticmethod
    def parse_series(series: str) -> tuple[str, str]:
        """
        :returns: series_name, number_in_series
        """
        if match := re.fullmatch(r"(.+?) #(\d+)", series):
            return match.group(1), match.group(2)
        return series, ""

    def get_book(self, url: str):
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        title = find_in_soup(soup, "main-info__title")
        author = find_in_soup(
            soup, "a.main-info__link[href^='/avtor']", _("unknown_author")
        )

        series_name, number_in_series = self.parse_series(
            find_in_soup(soup, "a.book-info__link[href^='/serie']")
        )

        description = find_in_soup(soup, "article")
        total_pages = int(
            find_in_soup(
                soup,
                ".button-pages__right",
                modification=lambda x: x.removesuffix(
                    "стр."
                ),  # Do not translate
            )
        )
        cover = soup.select_one(".book-image img").attrs["src"]
        file_url = soup.select_one(".download__item:not(.disabled) a").attrs[
            "href"
        ]

        return RawBook(
            title=safe_name(title),
            author=safe_name(author),
            series_name=safe_name(series_name),
            number_in_series=number_in_series,
            description=description,
            source=TextBook(
                url=url,
                cover=cover,
                publication="",
                file_url=file_url,
                total_pages=total_pages,
            ),
        )

    def get_book_series(self, url):
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")
        if not (el := soup.select_one("a.book-info__link[href^='/serie']")):
            return []  # book has no series
        series_page_link = self.site_url + el.attrs["href"]

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")

        books: list[BookPreview] = []
        for card in soup.select(".author"):
            if book := self._parse_book_card(card, _("unknown_author"), ""):
                books.append(book)

        return books

    def search_books(self, query, limit=10, offset=0):
        books: list[BookPreview] = []

        while True:
            if len(books) == limit:
                break

            payload = copy(self.SEARCH_PAYLOAD)
            payload["offset"] = offset
            payload["q"] = query

            data = self._session.post(self.SEARCH_URL, data=payload).json()
            offset = data["offset"]
            soup = BeautifulSoup(data["html"], "html.parser")

            if not (elements := soup.select(".book")):
                break
            for card in elements:
                if book := self._parse_book_card(card, _("unknown_author"), ""):
                    books.append(book)
                if len(books) == limit:
                    break

        return books

    def _parse_book_card(
        self, card: Tag, author: str, series_name: str
    ) -> BookPreview | None:
        with suppress(AttributeError, KeyError, TypeError):
            url = card.select_one("a.book__image").attrs["href"]
            cover = card.select_one("a.book__image img").attrs["src"]
            series_name, number_in_series = self.parse_series(
                find_in_soup(card, "a.book-info__link[href^='/serie']")
            )
            title = card.select_one(".book__title a").attrs["title"]
            author = find_in_soup(
                card, "a.main-info__link[href^='/avtor']", author
            )
            total_pages = find_in_soup(
                card,
                "a[href^='/chitat-online']",
                modification=lambda x: x.split(" — ")[1],
            )
            return BookPreview(
                title=safe_name(title),
                author=safe_name(author),
                series_name=safe_name(series_name),
                number_in_series=number_in_series,
                description="",
                url=self.site_url + url,
                cover=cover,
                narrator="",
                publication="",
                duration=total_pages,
            )

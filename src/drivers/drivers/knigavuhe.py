import re
from contextlib import suppress

import orjson
from bs4 import BeautifulSoup, Tag

from models.book import AudioBook, BookPreview, Chapter, RawBook

from ..base_driver import BaseDriver
from ..downloaders import MP3Downloader
from ..tools import find_in_soup, safe_name


class KnigaVUhe(BaseDriver[AudioBook]):
    site_url = "https://knigavuhe.org"
    downloader_factory = MP3Downloader

    PER_PAGE = 10

    def get_book(self, url: str):
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")
        page = page.text

        match = re.search(r"cur\.book = (.+);", page)
        book = orjson.loads(match.group(1))

        match = re.search(
            r"var player = new BookPlayer\(\d+, (\[.+?]).+\);", page
        )
        playlist = orjson.loads(match.group(1))

        title = book["name"]
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
        narrator = find_in_soup(soup, "a[href^='/reader/']")
        duration = ""
        with suppress(AttributeError, TypeError):
            duration = (
                soup.find("span", string="Время звучания:")
                .parent.contents[-1]
                .strip()
            )  # Do not translate
        cover = soup.select_one("div.book_cover > img").attrs["src"]

        chapters: list[Chapter] = []
        for i, item in enumerate(playlist):
            chapters.append(
                Chapter(
                    title=safe_name(item["title"]),
                    url=item["url"],
                    file_index=i,
                    start_time=0,
                    end_time=item["duration"],
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
        author = find_in_soup(
            soup, "span.book_title_elem > span > a", _("unknown_author")
        )

        if not (el := soup.select_one("div.book_serie_block_title > a")):
            return []  # book has no series
        series_page_link = self.site_url + el.attrs["href"]
        series_name = el.text

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")

        books: list[BookPreview] = []
        for card in soup.select(
            "div.bookkitem:not(:has(.bookkitem_litres_icon))"
        ):
            if book := self._parse_book_card(card, author, series_name):
                books.append(book)
                url = narrator = ""
                for element in card.select(
                    "div.bookkitem_other_versions_list > a"
                ):
                    if url == "":
                        url = self.site_url + element.attrs["href"]
                    elif narrator == "":
                        narrator = element.text
                        book.urls.add(url)
                        book.narrators.add(safe_name(narrator))
                        url = narrator = ""

        return books

    async def search_books(self, query, limit=10, offset=0):
        books: list[BookPreview] = []
        page_number = offset // self.PER_PAGE + 1
        offset %= self.PER_PAGE

        while len(books) < limit:
            url = self.site_url + f"/search/?q={query}&page={page_number}"

            async with self._async_session.get(url) as resp:
                page = await resp.text()
            soup = BeautifulSoup(page, "html.parser")

            if not (
                elements := soup.select(
                    "div.bookkitem:not(:has(span.bookkitem_litres_icon))"
                )
            ):
                break

            if offset:
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
        self, card: Tag, author: str, series_name: str
    ) -> BookPreview | None:
        with suppress(AttributeError, KeyError, TypeError):
            url = card.select_one("a.bookkitem_cover").attrs["href"]
            cover = card.select_one("img.bookkitem_cover_img").attrs["src"]
            number_in_series = find_in_soup(
                card,
                "span.bookkitem_serie_index",
                modification=lambda x: x.strip("."),
            )
            title = find_in_soup(card, "a.bookkitem_name")
            if number_in_series:
                title = title.removeprefix(f"{number_in_series}. ")
            author = find_in_soup(card, "span.bookkitem_author > a", author)
            narrator = find_in_soup(card, "a[href^='/reader/']")
            duration = find_in_soup(card, "span.bookkitem_meta_time")
            series_name = find_in_soup(card, "a[href^='/serie/']", series_name)
            return BookPreview(
                title=safe_name(title),
                author=safe_name(author),
                series_name=safe_name(series_name),
                number_in_series=number_in_series,
                description="",
                urls={self.site_url + url},
                cover=cover,
                narrators={safe_name(narrator)},
                publications=set(),
                durations=[duration],
            )

import re
import typing as ty
from contextlib import suppress

from bs4 import BeautifulSoup
from orjson import orjson

from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name


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
        author = _("unknown_author")
        if element := soup.select("span.book_title_elem > span > a"):
            author = element[0].text.strip()

        try:
            series_name = soup.select_one("div.book_serie_block_title > a").text.strip()
        except AttributeError:
            series_name = ""
        try:
            number_in_series = (
                soup.select_one("div.book_serie_block_item > span:has(+ strong)")
                .text.strip()
                .strip(".")
            )
        except AttributeError:
            number_in_series = ""

        description = soup.select_one("div.book_description").text.strip()
        reader = ""
        elements = soup.select("span.book_title_elem")
        for element in elements:
            children = element.select("*")
            if children:
                if children[0].text in ["читает", "читают"]:
                    reader = children[1].text.strip()
        duration = ""
        elements = soup.select("div.book_blue_block > div")
        for element in elements:
            info = element.select("span.book_info_label")
            if info:
                if info[0].text == "Время звучания:":
                    duration = element.text.replace("Время звучания:", "").strip()

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

        series_page_link = (
            self.site_url
            + soup.select_one("div.book_serie_block_title > a").attrs["href"]
        )
        series_name = soup.select_one("div.book_serie_block_title > a").text

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")

        books = []
        for book in soup.select("div.bookkitem_right"):
            try:
                number = book.select_one("span.bookkitem_serie_index").text
            except AttributeError:
                number = ""
            elem = book.select_one("div.bookkitem_name > a")
            url = self.site_url + elem.attrs["href"]
            name: str = elem.text
            if name.startswith(number):
                name = name[len(number) :].strip()
            if number.endswith("."):
                number = number[:-1]
            try:
                reader = book.select_one(
                    "div.bookkitem_meta_block:has(span.-reader) "
                    "> span.single_reader > a"
                ).text
            except AttributeError:
                reader = book.select_one(
                    "div.bookkitem_meta_block:has(span.-reader) > a"
                ).text
            books.append(
                Book(
                    name=safe_name(name),
                    url=url,
                    reader=safe_name(reader),
                    series_name=safe_name(series_name),
                    number_in_series=number,
                )
            )
            with suppress(AttributeError):
                url = name = reader = ""
                for elem in book.select("div.bookkitem_other_versions_list > *"):
                    if elem.name == "a":
                        if url == "":
                            url = self.site_url + elem.attrs["href"]
                            name = elem.text
                        elif reader == "":
                            reader = elem.text
                    else:
                        if url and reader:
                            books.append(
                                Book(
                                    name=safe_name(name),
                                    url=url,
                                    reader=safe_name(reader),
                                    series_name=safe_name(series_name),
                                    number_in_series=number,
                                )
                            )
                        url = reader = ""
                if url and reader:
                    books.append(
                        Book(
                            name=safe_name(name),
                            url=url,
                            reader=safe_name(reader),
                            series_name=safe_name(series_name),
                            number_in_series=number,
                        )
                    )

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

            elements = soup.select(
                "div#books_list > div.bookkitem:not(:has(span.bookkitem_litres_icon))"
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
                    url = el.select_one("a.bookkitem_cover").attrs["href"]
                    preview = el.select_one("img.bookkitem_cover_img").attrs["src"]
                    name = el.select_one("a.bookkitem_name").text.strip()
                    try:
                        author = el.select_one("span.bookkitem_author > a").text.strip()
                    except AttributeError:
                        author = _("unknown_author")
                    try:
                        reader = el.select_one(
                            "div.bookkitem_meta_block:has(span.-reader) a"
                        ).text.strip()
                    except AttributeError:
                        reader = "нет данных"
                    duration = el.select_one("span.bookkitem_meta_time").text.strip()
                    try:
                        series_name = el.select_one(
                            "div.bookkitem_meta_block:has(span.-serie) a"
                        ).text.strip()
                    except AttributeError:
                        series_name = ""
                    books.append(
                        Book(
                            author=safe_name(author),
                            name=safe_name(name),
                            series_name=safe_name(series_name),
                            reader=reader,
                            duration=duration,
                            url=self.site_url + url,
                            preview=preview,
                            driver=self.driver_name,
                        )
                    )
                    if len(books) == limit:
                        break

            page_number += 1

        return books

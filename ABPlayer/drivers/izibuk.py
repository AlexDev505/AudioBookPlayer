import re

from bs4 import BeautifulSoup
from orjson import orjson

from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name


class Izibuk(Driver):
    site_url = "https://izib.uk"
    downloader_factory = MP3Downloader

    def get_book(self, url: str) -> Book:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")
        page = page.text

        name = soup.select_one("span[itemprop='name']").text.strip()
        author = "Неизвестный автор"
        if element := soup.select_one("span[itemprop='author'] a"):
            author = element.text.strip()

        series_name = ""
        if element := soup.select_one("a[href^='/serie']"):
            series_name = element.text.strip()
        number_in_series = ""
        if element := soup.select_one(
            "div:has(>div>a[href^='/serie']) div:has(>strong) span"
        ):
            number_in_series = element.text.strip().removesuffix(".")

        description = soup.select_one("div[itemprop='description']").text.strip()

        reader = ""
        if elements := soup.select(
            "div:has(>div>span[itemprop='author']) a[href^='/reader']"
        ):
            reader = ", ".join(el.text.strip() for el in elements)

        duration = ""
        if element := soup.select_one(
            "div:has(>div>span[itemprop='author']) > div:last-child"
        ):
            duration = element.text.strip().removeprefix("Время: ")  # Do not translate

        preview = soup.select_one("img").attrs["src"]

        match = re.search(r"var player = new XSPlayer\(((\s*.*?)+?)\);", page)
        player = orjson.loads(match.group(1))
        files_host = f"https://{player["mp3_url_prefix"]}"
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
            reader=reader,
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=items,
        )

    def get_book_series(self, url: str) -> list[Book]:
        page = self.get_page(url)
        soup = BeautifulSoup(page.content, "html.parser")

        if not (element := soup.select_one("a[href^='/serie']")):
            return []
        series_page_link = element.attrs["href"]
        series_name = element.text.strip()

        page = self.get_page(series_page_link)
        soup = BeautifulSoup(page.content, "html.parser")

        books = []
        for book in soup.select("#books_list > div"):
            number = book.select_one("div").text.strip().removeprefix("#")
            element = book.select_one("div>a:not(:has(>img))")
            url = f"{self.site_url}{element.attrs["href"]}"
            name = element.text.strip()
            preview = book.select_one("img").attrs["src"]
            reader = ""
            if elements := book.select("a[href^='/reader']"):
                reader = ", ".join(element.text.strip() for element in elements)
            description = book.select_one("div:last-child>div:last-child").text.strip()
            books.append(
                Book(
                    name=safe_name(name),
                    series_name=safe_name(series_name),
                    number_in_series=number,
                    description=description,
                    reader=reader,
                    url=url,
                    preview=preview,
                    driver=self.driver_name,
                )
            )

        return books

    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        books = []
        page_number = 1

        while True:
            if len(books) == limit:
                break

            url = f"{self.site_url}/search?q={query}&p={page_number}"

            page = self.get_page(url)
            soup = BeautifulSoup(page.content, "html.parser")
            if not soup.select_one("#books_list > div a[href^='/book']"):
                return books
            elements = soup.select(
                "#books_list>div>div:not(:has(a[href^='/book']+span))"
            )

            if offset:
                if offset > len(elements):
                    offset -= len(elements)
                    elements.clear()
                else:
                    elements = elements[offset:]
                    offset = 0

            for book_card in elements:
                element = book_card.select_one("div>a[href^='/book']:not(:has(>img))")
                url = f"{self.site_url}{element.attrs["href"]}"
                name = element.text.strip()
                preview = book_card.select_one("img").attrs["src"]
                author = "Неизвестный автор"
                if element := book_card.select_one("a[href^='/author']"):
                    author = element.text.strip()
                reader = ""
                if elements := book_card.select("a[href^='/reader']"):
                    reader = ", ".join(element.text.strip() for element in elements)
                series_name = ""
                if element := book_card.select_one("a[href^='/serie']"):
                    series_name = element.text.strip()
                description = book_card.select_one(
                    "div:last-child>div:last-child"
                ).text.strip()
                books.append(
                    Book(
                        author=safe_name(author),
                        name=safe_name(name),
                        series_name=series_name,
                        reader=reader,
                        url=url,
                        preview=preview,
                        description=description,
                        driver=self.driver_name,
                    )
                )
                if len(books) == limit:
                    break

            page_number += 1

        return books

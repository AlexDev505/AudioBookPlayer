import json
import typing as ty
from contextlib import suppress

from selenium.common.exceptions import NoSuchElementException

from database.tables.books import Book, BookItems, BookItem
from .base import Driver


class KnigaVUhe(Driver):
    def get_book_series(self, url: str) -> ty.List[Book]:
        page = self.get_page(url)
        series_page_link = page.find_element_by_css_selector(
            "div.book_serie_block_title > a"
        ).get_attribute("href")
        series_name = page.find_element_by_css_selector(
            "div.book_serie_block_title > a"
        ).text
        page = self.get_page(series_page_link)

        books = []
        for book in page.find_elements_by_css_selector("div.bookkitem_right"):
            try:
                number = book.find_element_by_css_selector(
                    "span.bookkitem_serie_index"
                ).text
            except NoSuchElementException:
                number = ""
            elem = book.find_element_by_css_selector("div.bookkitem_name > a")
            url = elem.get_attribute("href")
            name: str = elem.text
            if name.startswith(number):
                name = name[len(number) :].strip()
            if number.endswith("."):
                number = number[:-1]
            try:
                reader = book.find_element_by_css_selector(
                    "div.bookkitem_meta_block:has(span.-reader) > span.single_reader > a"
                ).text
            except NoSuchElementException:
                reader = book.find_element_by_css_selector(
                    "div.bookkitem_meta_block:has(span.-reader) > a"
                ).text
            books.append(
                Book(
                    name=name,
                    url=url,
                    reader=reader,
                    series_name=series_name,
                    number_in_series=number,
                )
            )
            with suppress(NoSuchElementException):
                url = name = reader = ""
                for elem in book.find_elements_by_css_selector(
                    "div.bookkitem_other_versions_list > *"
                ):
                    if elem.tag_name == "a":
                        if url == "":
                            url = elem.get_attribute("href")
                            name = elem.text
                        elif reader == "":
                            reader = elem.text
                    else:
                        if url and reader:
                            books.append(
                                Book(
                                    name=name,
                                    url=url,
                                    reader=reader,
                                    number_in_series=number,
                                )
                            )
                        url = reader = ""
                if url and reader:
                    books.append(
                        Book(name=name, url=url, reader=reader, number_in_series=number)
                    )

        return books

    def get_book(self, url: str) -> Book:
        page = self.get_page(url)

        page.execute_script(
            f"""
            var playlist = document.createElement("div");
            playlist.id = "playlist";
            playlist.innerHTML = JSON.stringify(cur["bookPlayer"]["playlist"]);
            document.body.append(playlist);
            """
        )

        playlist = page.find_element_by_id("playlist").text.replace("\n", "")
        playlist = json.loads(playlist)

        name = page.find_elements_by_css_selector("span.book_title_name")[0].text
        author = page.find_elements_by_css_selector("span.book_title_elem > span > a")[
            0
        ].text.strip()
        try:
            series_name = page.find_element_by_css_selector(
                "div.book_serie_block_title > a"
            ).text.strip()
        except NoSuchElementException:
            series_name = ""
        try:
            number_in_series = (
                page.find_element_by_css_selector(
                    "div.book_serie_block_item > span:has(+ strong)"
                )
                .text.strip()
                .strip(".")
            )
        except NoSuchElementException:
            number_in_series = ""

        description = page.find_elements_by_css_selector("div.book_description")[
            0
        ].text.strip()
        reader = ""
        elements = page.find_elements_by_css_selector("span.book_title_elem")
        for element in elements:
            children = element.find_elements_by_css_selector("*")
            if children:
                if children[0].text == "читает":
                    reader = children[1].text
        duration = ""
        elements = page.find_elements_by_css_selector("div.book_blue_block > div")
        for element in elements:
            info = element.find_elements_by_css_selector("span.book_info_label")
            if info:
                if info[0].text == "Время звучания:":
                    duration = element.text.replace("Время звучания:", "").strip()

        preview = page.find_elements_by_css_selector("div.book_cover > img")[
            0
        ].get_attribute("src")

        items = BookItems()
        for i, item in enumerate(playlist):
            items.append(
                BookItem(
                    file_url=item["url"],
                    file_index=i + 1,
                    title=item["title"],
                    start_time=0,
                    end_time=item["duration"],
                )
            )

        return Book(
            author=author,
            name=name,
            series_name=series_name,
            number_in_series=number_in_series,
            description=description,
            reader=reader,
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=items,
        )

    @classmethod
    @property
    def site_url(cls):
        return "https://knigavuhe.org/"

import json
import typing as ty

from database.tables.books import Book, BookItems, BookItem
from .base import Driver


class KnigaVUhe(Driver):
    def get_book_series(self, url: str) -> ty.List[Book]:
        page = self.get_page(url)

        books = [
            Book(name=book.text, url=book.get_attribute("href"))
            for book in page.find_elements_by_css_selector(
                "div.book_serie_block_item > a"
            )
        ]

        # Книга может быть одной из серии
        if not len(books):
            books = [
                Book(
                    url=url,
                    name=page.find_elements_by_css_selector("span.book_title_name")[
                        0
                    ].text,
                )
            ]

        page.quit()

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
                    end_time=0,
                )
            )

        page.quit()

        return Book(
            author=author,
            name=name,
            description=description,
            reader=reader,
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=items,
        )

    @property
    def site_url(self):
        return "https://knigavuhe.org/"

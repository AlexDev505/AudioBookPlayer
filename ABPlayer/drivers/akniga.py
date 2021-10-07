import json
import typing as ty

from database import Book, BookItems, BookItem
from .base import Driver


class AKnigaDriver(Driver):
    def get_book(self, url: str) -> Book:
        page = self.get_page(url)

        bid = page.find_elements_by_css_selector("article.ls-topic.js-topic")[
            0
        ].get_attribute(
            "data-bid"
        )  # ID книги

        page.execute_script(
            f"""
            var data = document.createElement("div");
            data.id = "data";
            data.innerHTML = JSON.stringify(bookData);
            document.body.append(data);
            """
        )

        data = page.find_element_by_id("data").text.replace("\n", "")
        data = json.loads(data)[bid]

        author = data["author"]
        name = data["titleonly"]
        preview = data["preview"]
        items = BookItems()
        for item in data["items"]:
            items.append(
                BookItem(
                    file_url=f"{data['srv']}/b/{bid}/{data['key']}/"
                    f"{str(item['file']).rjust(2, '0')}. {data['title']}.mp3",
                    file_index=item["file"],
                    title=item["title"],
                    start_time=item["time_from_start"],
                    end_time=item["time_finish"],
                )
            )

        page.quit()

        return Book(author, name, url, preview, self.driver_name, items)

    def get_book_series(self, url: str) -> ty.List[Book]:
        page = self.get_page(url)

        books = [
            Book(
                url=book.get_attribute("href"),
                name=book.find_elements_by_css_selector(".caption")[0].get_attribute(
                    "innerHTML"
                ),
            )
            for book in page.find_elements_by_css_selector(
                ".content__main__book--item--series-list > a"
            )
        ]

        # Книга может быть одной из серии
        if not len(books):
            books = [
                Book(
                    url=url,
                    name=page.find_elements_by_css_selector(".caption__article-main")[
                        0
                    ].text,
                )
            ]

        page.quit()

        return books

    @property
    def site_url(self):
        return "https://akniga.org/"

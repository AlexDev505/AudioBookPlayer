import json

from selenium.common.exceptions import NoSuchElementException

from database import BookItems, BookItem
from .base import Driver


class AKnigaDriver(Driver):
    def get_book(self, url: str) -> dict:
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
        description = (
            page.find_elements_by_css_selector("div.description__article-main")[0]
            .text.replace("ОПИСАНИЕ", "")
            .strip()
        )
        try:
            series_name = page.find_element_by_css_selector(
                "span.caption__article-main--book:"
                "has(+ div.content__main__book--item--series-list) > a"
            ).text.strip()
            number_in_series = (
                page.find_element_by_css_selector(
                    "div.content__main__book--item--series-list > a.current > b"
                )
                .text.strip()
                .strip(".")
            )
        except NoSuchElementException:
            series_name = ""
            number_in_series = ""

        duration = " ".join(
            [
                obj.text
                for obj in page.find_elements_by_css_selector(
                    "span[class*='book-duration-'] > span"
                )
            ]
        ).strip()
        reader = page.find_elements_by_css_selector("a.link__reader span")[0].text
        preview = page.find_elements_by_css_selector("div.book--cover img")[
            0
        ].get_attribute("src")
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

        return dict(
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
        return "https://akniga.org/"
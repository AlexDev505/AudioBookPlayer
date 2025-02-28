import typing as ty

from selenium import webdriver

from database import Book, BookItems, BookItem
from .base import Driver
import json


class AKniga(Driver):
    @property
    def driver(self) -> ty.Union[ty.Type[webdriver.Chrome], ty.Type[webdriver.Firefox]]:
        return webdriver.Chrome

    @property
    def driver_path(self) -> str:
        return r"drivers\chromedriver"

    @property
    def driver_options(
        self,
    ) -> ty.Union[webdriver.ChromeOptions, webdriver.FirefoxOptions]:
        options = webdriver.ChromeOptions()
        options.add_argument("headless")
        options.add_argument("disable-gpu")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        return options

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
                    title=item["title"],
                    start_time=item["time_from_start"],
                    end_time=item["time_finish"],
                )
            )

        page.quit()

        return Book(author, name, url, preview, self.driver_name, items)

    @property
    def site_url(self):
        return "https://akniga.org/"

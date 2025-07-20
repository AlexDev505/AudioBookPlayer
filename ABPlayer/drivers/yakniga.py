import re
import typing as ty
from contextlib import suppress
from copy import deepcopy

import requests
from models.book import Book, BookItem, BookItems
from tools import ttl_cache

from .base import Driver
from .downloaders import MP3Downloader
from .tools import duration_sec_to_str, safe_name


class Yakniga(Driver):
    site_url = "https://yakniga.org"
    downloader_factory = MP3Downloader

    api_url = "https://yakniga.org/graphql"
    # GraphQL queries
    book_fields = """
        title
        authorName
        readers { name }
        seriesName
        seriesNum
        duration
        cover
        description
        authorAlias
        aliasName
        isBiblio
    """
    # bookAlias and authorAliasName can be obtained from url to the book
    get_book_payload = {
        "operationName": "getBook",
        "variables": {"bookAlias": "", "authorAliasName": ""},
        "query": """
            query getBook($bookAlias: String, $authorAliasName: String) {
                book(aliasName: $bookAlias, authorAliasName: $authorAliasName) {
                    %s
                    chapters {
                        collection {
                            name
                            duration
                            fileUrl
                        }
                    }
                }
            }
        """
        % book_fields,
    }
    # by_series - series name
    get_book_series_payload = {
        "operationName": "bookCollection",
        "variables": {"query": {"by_series": ""}, "page": 1, "perPage": 100},
        "query": """
            query bookCollection($query: JSON, $perPage: Int, $page: Int) {
                books(query: $query, perPage: $perPage, page: $page) {
                    collection {
                        %s
                    }
                }
            }
        """
        % book_fields,
    }
    # term - search query
    search_payload = {
        "operationName": None,
        "variables": {"term": ""},
        "query": """
            query ($term: String!) {
                search(autocomplete: true, term: $term) {
                    ... on Book {
                       %s
                    }
                }
            }
        """
        % book_fields,
    }

    def get_book(self, url: str) -> Book:
        data = self._get_book_data(url)
        book = self._parse_book_data(data, supress_exc=False)

        items = BookItems()
        for i, item in enumerate(data["chapters"]["collection"]):
            items.append(
                BookItem(
                    file_url=f"{self.site_url}{item['fileUrl']}",
                    file_index=i,
                    title=safe_name(item["name"]),
                    start_time=0,
                    end_time=item["duration"],
                )
            )
        book.items = items

        return book

    def get_book_series(self, url: str) -> ty.List[Book]:
        # getting series name
        data = self._get_book_data(url)
        if not (series_name := data.get("seriesName")):
            return []

        # search books by series
        payload = deepcopy(self.get_book_series_payload)
        payload["variables"]["query"]["by_series"] = series_name
        data = requests.post(self.api_url, json=payload).json()
        books_data = data["data"]["books"]["collection"]

        books = []
        for book_data in books_data:
            if book := self._parse_book_data(book_data):
                books.append(book)

        return books

    def search_books(
        self, query: str, limit: int = 10, offset: int = 0
    ) -> list[Book]:
        books = []

        if not (data := self._search(query)):
            return books

        for card in data[offset:]:
            if book := self._parse_book_data(card):
                books.append(book)
            if len(books) == limit:
                break

        return books

    def _get_book_data(self, url: str) -> dict:
        author_alias, book_alias = url.split("/")[-2:]
        payload = deepcopy(self.get_book_payload)
        payload["variables"]["bookAlias"] = book_alias
        payload["variables"]["authorAliasName"] = author_alias
        data = requests.post(self.api_url, json=payload).json()
        return data["data"]["book"]

    def _parse_book_data(
        self, data: dict, supress_exc: bool = True
    ) -> Book | None:
        with suppress(
            *(AttributeError, KeyError, TypeError, IndexError)
            if supress_exc
            else ()
        ):
            if data["isBiblio"]:
                raise KeyError("licensed book")
            url = f"/{data['authorAlias']}/{data['aliasName']}"
            name = data["title"]
            author = data.get("authorName", _("unknown_author"))
            series_name = data.get("seriesName", "")
            if number_in_series := data.get("seriesNum", ""):
                # in this site numbers in series usually represented in float
                with suppress(ValueError):
                    if float(number_in_series) == int(number_in_series):
                        number_in_series = str(int(number_in_series))
            if description := data.get("description", ""):
                description = re.sub(r"<p>(.+?)</p>", r"\g<1>", description)
            reader = data["readers"][0]["name"] if "readers" in data else ""
            duration = duration_sec_to_str(data.get("duration", 0))
            preview = data.get("cover", "")
            preview = f"{self.site_url}{preview}" if preview else ""

            return Book(
                author=safe_name(author),
                name=safe_name(name),
                series_name=safe_name(series_name),
                number_in_series=number_in_series,
                description=description,
                reader=safe_name(reader),
                duration=duration,
                url=self.site_url + url,
                preview=preview,
                driver=self.driver_name,
            )

    @ttl_cache(600)
    def _search(self, query: str) -> list[dict]:
        payload = deepcopy(self.search_payload)
        payload["variables"]["term"] = query
        data = requests.post(self.api_url, json=payload).json()
        # The result also includes authors, series, etc., but have empty dicts
        return [x for x in data["data"]["search"] if x]

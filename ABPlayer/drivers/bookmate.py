import os.path
import time
import urllib.parse
from contextlib import suppress
from pathlib import Path

import requests
import webview

from models.book import Book, BookItems, BookItem
from .base import LicensedDriver, DriverNotAuthenticated
from .downloaders.m3u8_downloader import M3U8Downloader
from .tools import duration_sec_to_str, safe_name


class Bookmate(LicensedDriver):
    site_url = "https://books.yandex.ru/"
    api_url = "https://api.bookmate.yandex.net/api/v5/"
    downloader_factory = M3U8Downloader

    headers = {"auth-token": ""}

    @classmethod
    def _load_auth(cls) -> bool:
        if not os.path.exists(cls.AUTH_FILE):
            return False
        with open(cls.AUTH_FILE, encoding="utf-8") as f:
            data = f.read()
        if not data:
            return False
        cls.headers = {"auth-token": data}
        return True

    @classmethod
    def _auth(cls) -> bool:
        def _on_loaded():
            while True:
                if window.get_current_url() is None:
                    break
                if window.get_current_url().startswith(
                    "https://yx4483e97bab6e486a9822973109a14d05.oauth.yandex.ru/"
                ):
                    return _extract_token()
                time.sleep(1)

        def _on_closed():
            window.active = False

        def _extract_token():
            url = urllib.parse.urlparse(window.get_current_url())
            window.token = urllib.parse.parse_qs(url.fragment)["access_token"][0]
            window.destroy()

        window = webview.create_window(
            "",
            url="https://oauth.yandex.ru/authorize?response_type=token"
            "&client_id=4483e97bab6e486a9822973109a14d05",
        )
        window.events.loaded += _on_loaded
        window.events.closed += _on_closed
        window.active = True
        window.token = ""
        # Currently, there are no running pywebview windows
        if len(webview.windows) == 1:
            webview.start()
        else:
            while window.active:
                time.sleep(1)

        if window.token:
            Path(cls.AUTH_FILE).parent.mkdir(parents=True, exist_ok=True)
            with open(cls.AUTH_FILE, "w", encoding="utf-8") as f:
                f.write(window.token)
            cls.headers = {"auth-token": window.token}
            return True
        return False

    def get_book(self, url: str) -> Book:
        book_uuid = url.split("/")[-1]
        book_data = requests.get(f"{self.api_url}/audiobooks/{book_uuid}").json()[
            "audiobook"
        ]

        if not (book := self._parse_book_data(book_data, "", "")):
            raise ValueError
        resp = requests.get(
            f"{self.api_url}/audiobooks/{book_uuid}/playlists.json",
            headers=self.headers,
        ).json()
        if resp.get("error") == "not_authenticated":
            raise DriverNotAuthenticated()
        tracks = resp["tracks"]

        items = BookItems()
        for i, item in enumerate(tracks):
            items.append(
                BookItem(
                    file_url=item["offline"]["max_bit_rate"]["url"],
                    file_index=i,
                    title=f"Глава {i + 1}",
                    start_time=0,
                    end_time=item["duration"]["seconds"],
                )
            )
        book.items = items

        return book

    def get_book_series(self, url: str) -> list[Book]:
        book_uuid = url.split("/")[-1]
        book_data = requests.get(f"{self.api_url}/audiobooks/{book_uuid}").json()[
            "audiobook"
        ]
        if not (series := book_data.get("series_list")):
            return []

        series = series[0]
        series_name = series.get("title")
        books_data = requests.get(
            f"https://api.bookmate.yandex.net/api/v5/series/{series["uuid"]}/parts"
        ).json()["parts"]

        books = []
        for book_data in books_data:
            if book := self._parse_book_data(
                book_data["resource"], series_name, book_data["position_label"]
            ):
                books.append(book)

        return books

    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        books = []
        page_number = 1
        while True:
            if len(books) == limit:
                break

            url = f"{self.api_url}/audiobooks/search?query={query}&page={page_number}"
            if not (books_data := requests.get(url).json()["objects"]):
                break

            if offset:
                if offset > len(books_data):
                    offset -= len(books_data)
                    books_data.clear()
                else:
                    books_data = books_data[offset:]
                    offset = 0

            for book_data in books_data:
                if book := self._parse_book_data(book_data, "", ""):
                    books.append(book)
                if len(books) == limit:
                    break

            page_number += 1

        return books

    def _parse_book_data(
        self, book_data: dict, series_name: str, number_in_series: str
    ) -> Book | None:
        with suppress(KeyError, IndexError):
            url = f"{self.site_url}/audiobooks/{book_data["uuid"]}"
            author = book_data["authors"][0]["name"] if "authors" in book_data else ""
            name = book_data["title"]
            series_name = (
                book_data["series_list"][0]["title"]
                if book_data.get("series_list")
                else series_name
            )
            number_in_series = (
                book_data["series_list"][0]["position_label"]
                if book_data.get("series_list")
                else number_in_series
            )
            reader = (
                book_data["narrators"][0]["name"] if "narrators" in book_data else ""
            )
            duration = duration_sec_to_str(book_data.get("duration", 0))
            preview = (
                book_data["cover"].get("large", book_data["cover"].get("small", ""))
                if "cover" in book_data
                else ""
            )
            description = book_data.get("annotation", "")
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
            )

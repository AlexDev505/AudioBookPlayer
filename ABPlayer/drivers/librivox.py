import typing as ty
from math import floor
from urllib.parse import quote as urlize

from cachetools import TTLCache
from models.book import Book, BookItem, BookItems
from requests import Session
from requests_ratelimiter import LimiterAdapter

from .base import Driver
from .downloaders import MP3Downloader
from .tools import html_to_text, safe_name

# moderate, non aggressive strategy
RATE_LIMIT = 5  # Beyond this would be too much.
CACHE_SIZE = 50  # not too big but enough for some tab switch and search
CACHE_LIFE = 600  # Short life prevents stale data. 10 min for an archive is ok.
# a bigger and longer lived cache would warrant a UI to clear it.
SELECTED_FORMAT = "128Kbps MP3"
# "128Kbps MP3" is the original format of LibriVox collection, ~ CD quality.
# Refer : https://archive.org/post/1053663/file-format


class LibriVox(Driver):
    """
    Driver for LibriVox.
    Making use of the internetarchive metadata API to browse/fetch audiobooks
    from the LibriVox collection on archive.org.
    while the respecting API rate limit.
    """

    site_url = "https://archive.org"
    downloader_factory = MP3Downloader

    session = Session()
    # cache can be cleared with class_obj.cache.clear()
    cache = TTLCache(maxsize=CACHE_SIZE, ttl=CACHE_LIFE)
    ratelimit_adapter = LimiterAdapter(per_second=RATE_LIMIT)
    session.mount(site_url, ratelimit_adapter)

    def _get(self, url):
        if url in self.cache:
            return self.cache[url]

        response = self.session.get(url)
        if response.status_code == 200:
            self.cache[url] = response
            return response

    def get_book(self, url: str) -> Book:
        """
        This method uses 'session' to
        fetch metadata for an archive.org audiobook, specifically from the-
        -Librivox collection.
        The URL of the audiobook is passed into this function.

        Args:
            url (str): The URL of the audiobook on archive.org.
            This URL is used to fetch metadata and chapter information-
                                                    -for the audiobook.
        Returns:
           Book: A Book object containing metadata
           and chapter information for the audiobook.
        """
        identifier = url.strip("/").split("/")[-1]
        response = self._get(f"{self.site_url}/metadata/{identifier}")
        meta_item = response.json()
        metadata = meta_item["metadata"]
        files = meta_item["files"]

        author = metadata.get("creator", _("unknown_author"))
        if isinstance(author, list):
            author = author[0]
        title = metadata["title"]
        duration = metadata.get("runtime", "")
        description = html_to_text(metadata.get("description", ""))

        preview = ""
        # only one jpg file i.e. cover img has label "JPEG".
        if cover_filename := next(
            (item["name"] for item in files if item["format"] == "JPEG"), None
        ):
            preview = f"{self.site_url}/download/{identifier}/{cover_filename}"

        chapters = BookItems()
        for i, file in enumerate(
            filter(lambda item: item["format"] == SELECTED_FORMAT, files)
        ):
            file_url = f"{self.site_url}/download/{identifier}/{file['name']}"
            chapter_title = file.get("title")
            end_time = floor(float(file["length"]))
            chapters.append(
                BookItem(
                    file_url=file_url,
                    file_index=i + 1,
                    title=safe_name(chapter_title),
                    start_time=0,
                    end_time=end_time,
                )
            )

        return Book(
            author=safe_name(author),
            name=safe_name(title),
            series_name="",
            number_in_series="",
            description=description,
            reader="",  # This information is available on librivox.org
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=chapters,
        )

    def search_books(
        self, query: str, limit: int = 20, offset: int = 0
    ) -> ty.List[Book]:
        """
        Args:
            query: search terms
            limit: limit-maximum books to return
            offset: how many books to skip from the first page of results.
                helps determining pagination.
        Returns:
            ty.List[Book]: A list of Book objects containing metadata
            for audiobooks that match the search query
        """
        books = []
        page_number = 1

        while True:
            if len(books) >= limit:
                break

            url = (
                "https://archive.org/advancedsearch.php?q=title:"
                f"({urlize(query.lower())})"
                f'AND+collection:"librivoxaudio"&fl[]=creator&fl[]=identifier'
                f"&fl[]=title&rows={limit}&page={page_number}&output=json"
            )  # The query is case insensitive because of the parnthesis.
            # normalizing the case makes cacheing more efficient

            response = self._get(url).json()
            if not (hits := response["response"]["docs"]):
                break

            if offset:
                if offset >= len(hits):
                    offset -= len(hits)
                    hits.clear()
                else:
                    hits = hits[offset:]
                    offset = 0

            for hit in hits:
                author = hit.get("creator", _("unknown_author"))
                name = hit.get("title")
                url = f"https://archive.org/details/{hit['identifier']}"
                preview = (
                    f"https://archive.org/services/img/{hit['identifier']}"
                )
                books.append(
                    Book(
                        author=safe_name(author),
                        name=safe_name(name),
                        url=url,
                        preview=preview,
                        driver=self.driver_name,
                    )
                )
                if len(books) >= limit:
                    break

            page_number += 1

        return books

    def get_book_series(self, url: str) -> ty.List[Book]:
        """ """
        return []

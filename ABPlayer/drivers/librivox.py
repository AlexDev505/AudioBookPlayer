import typing as ty
from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name, hms_to_sec, html_to_text
from math import floor
from requests_ratelimiter import LimiterAdapter
from urllib.parse import quote as urlize
from requests import Session
from cachetools import TTLCache

# moderate, non aggressive strategy
RATE_LIMIT = 5  # Beyond this would be too much.
CACHE_SIZE=50 #not too big but enough for some tab switch and search
CACHE_LIFE=600 #Short life prevents stale data. 10 min for an archive is ok.
#a bigger and longer lived cache would warrant a UI to clear it.
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
    session=Session()
    #cache can be cleared with class_obj.cache.clear()
    cache=TTLCache(maxsize=CACHE_SIZE,ttl=CACHE_LIFE)
    ratelimit_adapter = LimiterAdapter(per_second=RATE_LIMIT)
    session.mount(site_url, ratelimit_adapter)

    def __init__(self):
        super().__init__()

    def get(self,url):
        try:
            if url in self.cache:
                return self.cache[url]
            else:
                response = self.session.get(url)
                if response.status_code == 200:
                    self.cache[url]=response
                    return response
                else:
                    response.raise_for_status()
        except Exception as e:
            return

    def get_book(self, url: str) -> Book:
        """
        This method uses  'session' to
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
        response = self.get(f"{self.site_url}/metadata/{identifier}")
        meta_item = response.json()
        keys = meta_item.keys()
        if "metadata" in keys:
            metadata = meta_item["metadata"]
            if not 'creator' in metadata.keys() or not 'title' in metadata.keys():
                return None
            author = metadata["creator"]
            if isinstance(author, list):
                author = ", ".join(author)
            else:
                author = str(author)  # The usual (single name) or unknown type.
            title = metadata["title"]
            duration = metadata.get("runtime", "No Data")
            description = html_to_text(metadata.get("description", "No Data"))

        if "files" in meta_item.keys():
            files = meta_item["files"]
            cover_filename = next(
                (item["name"] for item in files if item["format"] == "JPEG"),
                None,
                # only one jpg file i.e. cover img has label "JPEG".
            )
            preview = (
                f"{self.site_url}/download/{identifier}/{cover_filename}"
                if cover_filename
                else "No Data"
            )
        chapters = BookItems()
        audiofiles = [file for file in files if file["format"] == SELECTED_FORMAT]
        for file in audiofiles:
            file_url, file_index, end_time = (
                None,
                0,
                None
            )
            keys = file.keys()
            if "name" in keys:
                file_url = f"{self.site_url}/download/{identifier}/" f"{file['name']}"
            if "title" in keys:
                chapter_title = file["title"]
            if "length" in keys:
                if (
                    file["format"] == "64Kbps MP3"
                ):  # lengthetadata for "64Kbps MP3" files is in hh:mm:ss format
                    end_time = hms_to_sec(file["length"])
                elif file["format"] == "128Kbps MP3":
                    end_time = floor(float(file["length"]))
                    # lengthetadata for "64Kbps MP3" files is in seconds(float)
                chapters.append(
                    BookItem(
                        file_url=file_url,
                        file_index=file_index,
                        title="No Data" if not chapter_title else chapter_title,
                        start_time=0,
                        end_time=end_time,
                    )
                )
        return Book(
            author=author,
            name=title,
            series_name="",
            number_in_series="",
            description=description,
            reader="No Data",  # This information is available on librivox.org
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
            search terms
            limit-maximum books to return
            offset: how many books to skip from the first page of results. . helps determining pagination
            offset
        Returns:
            ty.List[Book]: A list of Book objects containing metadata
            for audiobooks that match the search query

        """

        books = []
        page_number = 1

        while True:
            if len(books) >= limit:
                break
                # query planned by AlexDev505. I removed
                # 'title:' and made it more generic.
                # User can now be more generic or specific.
            url = (
                f"https://archive.org/advancedsearch.php?q=title:({urlize(query.lower())})"
                f'AND+collection:"librivoxaudio"&fl[]=creator&fl[]=identifier'
                f"&fl[]=title&rows={limit}&page={page_number}&output=json"
            )   # The query is case insensitive because of the parnthesis.
                # normalizing the case makes cacheing more efficient

            response = self.get(url)
            if "response" not in response.json():
                break

            if not (hits:= response.json()["response"]["docs"]):
                break

            if offset:
                if offset >= len(hits):
                    offset -= len(hits)
                    hits.clear()
                else:
                    hits = hits[offset:]
                    offset = 0

            for hit in hits:
                author = hit.get("creator", "Unknown Author")
                name = hit.get("title", "Unknown Title")
                url = f"https://archive.org/details/{hit['identifier']}"
                preview = f"https://archive.org/services/img/{hit['identifier']}"
                books.append(
                    Book(
                        author=safe_name(author),
                        name=safe_name(name),
                        url=url,
                        preview=preview,
                        driver=self.driver_name,
                        duration="No Data",
                    )
                )
                if len(books) >= limit:
                    break

            page_number += 1

        return books

    def get_book_series(self, url: str) -> ty.List[Book]:
        """
        to be implemented

        Placeholder to enable class instantiation.
        """
        books = []
        return books

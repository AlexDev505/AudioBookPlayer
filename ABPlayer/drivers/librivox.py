import typing as ty
from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name, hms_to_sec, html_to_text
from math import floor
from requests_ratelimiter import LimiterAdapter
from urllib.parse import quote as urlize
from requests import Session


# moderate, non aggressive strategy
RATE_LIMIT = 5  # Beyond this would be too much.
CACHE_SIZE=50
SELECTED_FORMAT = "128Kbps MP3"
# "128Kbps MP3" is the original format of LibriVox collection, ~ CD quality.
# Refer : https://archive.org/post/1053663/file-format
from collections import OrderedDict

from collections import OrderedDict

class FIFOCache:
    def __init__(self, maxsize=128):
        self.capacity = maxsize
        self.data = OrderedDict()

    def __setitem__(self, key, value):
        # Add or update a key-value pair, handling eviction
        if key in self.data:
            del self.data[key]
        elif len(self.data) >= self.capacity:
            self.data.popitem(last=False)  # FIFO eviction
        self.data[key] = value

    def __getitem__(self, key):
        # Retrieve a value for the given key
        if key in self.data:
            return self.data[key]
        raise KeyError(f"Key '{key}' not found in cache.")

    def __delitem__(self, key):
        # Remove a specific key-value pair
        if key in self.data:
            del self.data[key]
        else:
            raise KeyError(f"Key '{key}' not found in cache.")

    def __contains__(self, key):
        # Check if a key exists in the cache
        return key in self.data

    def __repr__(self):
        # Provide a string representation for debugging
        return f"FIFOCache({self.data})"



class LibriVox(Driver):
    """
    Driver for LibriVox.
    Making use of the internetarchive metadata API to browse/fetch audiobooks
    from the LibriVox collection on archive.org.
    while the respecting API rate limit.

    """

    site_url = "https://archive.org"
    downloader_factory = MP3Downloader
    ratelimit_adapter = LimiterAdapter(per_second=RATE_LIMIT)
    session = Session()
    session.mount(site_url, ratelimit_adapter)


    def __init__(self):
        super().__init__()
        self.cache=FIFOCache(maxsize=CACHE_SIZE)

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
        This method uses  'self.session' to
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
            file_url, file_index, chatper_title, start_time, end_time = (
                None,
                0,
                None,
                None,
                None,
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
                f"https://archive.org/advancedsearch.php?q=title:({urlize(query)})"
                f'AND+collection:"librivoxaudio"&fl[]=creator&fl[]=identifier'
                f"&fl[]=title&rows={limit}&page={page_number}&output=json"
            )

            response = self.get(url)
            if "response" not in response.json():
                break
            hits = response.json()["response"]["docs"]

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

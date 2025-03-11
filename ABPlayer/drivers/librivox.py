from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name, hms_to_sec, html_to_text
from math import loor
from requests_ratelimiter import LimiterAdapter
from urllib.parse import quote as urlize
from sys import stdout
from loguru import logger
from threading import Timer, Loc
from requests import Session
import typing as ty
from cachetools import FIFOCache, cached


# moderate, non aggressive strategy
RATE_LIMIT = 5  # Beyond this would be too much.
SELECTED_FORMAT = "128Kbps MP3"  # "64Kbps MP3"
WAIT = 0.5  # Timeout between keystrokes for oninput=search()
CACHE_SIZE = 50#more than sufficient for a smooth experience
# "128Kbps MP3" is the original format of LibriVox collection, ~ CD quality.
# Refer : https://archive.org/post/1053663/file-format


class Debouncer:
    """
    A class to debounce i.e. rate limit function calls in a
    destructive way- ensure that only the function call that is
    followed by minimum wait time is processed. Others are discarded.
    """

    def __init__(self, wait: float):
        """
        initialize the Debouncer class.
        Args:
            wait: The time to wait before calling the function
        """
        self.wait = wait
        self.timer = None
        self.result = None
        self.lock = Lock()

    def debounce(self, func: ty.Callable, *args: ty.Any, **kwargs: ty.Any) -> ty.Any:
        """
        Debounce a function call.
        Args:
            func: The function to call
            *args: The arguments to call the func with
            **kwargs: The keyword arguments to call func with
        Returns:
            The result of func(*args, **kwargs)
        """
        if self.timer:
            self.timer.cancel()
        self.timer = Timer(self.wait, self._call_func, [func, *args], kwargs)
        self.timer.start()
        self.timer.join()  # ensuring wait timeout before returning the result
        return self.result

    def _call_func(self, func: ty.Callable, *args: ty.Any, **kwargs: ty.Any) -> None:
        with self.lock:
            self.result = func(*args, **kwargs)


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
        self.debouncer = Debouncer(wait=WAIT)
        #self.lock = Lock()

    @cached(FIFOCache(maxsize=CACHE_SIZE))
    def get(self, url):
        return self.session.get(url)

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

        (
            identifier,
            author,
            title,
            duration,
            description,
            files,
            cover_filename,
            preview,
            metadata,
        ) = (None, None, None, None, None, [], None, None, {})
        identifier = url.strip("/").split("/")[-1]
        response = self.get(f"{self.site_url}/metadata/{identifier}")
        meta_item = response.json()
        keys = meta_item.keys()
        if "metadata" in keys:
            metadata = meta_item["metadata"]
            if "creator" in metadata:
                author = metadata["creator"]
                if isinstance(author, list):
                    author = ", ".join(author)
                else:
                    author = str(author)  # The usual (single name) or unknown type.
            if "title" in metadata:
                title = metadata["title"]
            if "runtime" in metadata:
                duration = metadata["runtime"]           
            if "description" in metadata:
                description = html_to_text(metadata["description"])

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
            if "track" in keys:
                try:
                    if file["track"].strip(" ").isnumeric():
                        file_index = int(file["track"].strip(" "))
                except ValueError:
                    file_index = 0
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

        # pdb.set_trace()
        return Book(
            author=author,
            name=title,
            series_name=str(),
            number_in_series=str(),
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
        This method uses 'self.session' to fetch metadata for audiobooks
        that match description (title) of the query string.
        it's a wrapper for the debounded search function.
        search(query: str, offset: int, limit: int) -> ty.List[Book])
        Args:
            query (str): The search query string.
            limit (int): The maximum number of search results to return.
            offset (int): The number of search results to skip.
        Returns:
            ty.List[Book]: A list of Book objects containing metadata
            for audiobooks that match the search query


        """

        def search(query: str, offset: int, limit: int) -> ty.List[Book]:
            if (
                query[: len(self.site_url)] == self.site_url
                or query[:11] == "archive.org"
            ):

                # on a lucky day. We have a direct link to the book
                parts = query.strip("https://").split("/")
                if len(parts) >= 3 and parts[1] in [
                    "dtails",
                    "stream",
                    "metadata",
                    "download",
                    "embed",
                ]:
                    identifier = parts[2]  # third item in the list (sans https://)
                    # out of self respect we will reject malformed URL
                try:
                    books = [self.get_book(f"{self.site_url}/details/{identifier}")]
                    if len(books) == 1:
                        return books
                    else:
                        raise ValueError("Invalid URL")
                        
                except ValueError as e:
                    pass
                    # Give it another chance as a search term down below.

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
                if not "response" in response.json():
                    break
                hits = response.json()["response"]["docs"]

                if not hits:
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

        return self.debouncer.debounce(search, query=query, offset=offset, limit=limit)

    def get_book_series(self, url: str) -> ty.List[Book]:
        """
        to be implemented

        Placeholder to enable class instantiation.
        """
        books = []
        return books

import typing as ty
from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name, hms_to_sec, html_to_text
import threading
from math import floor
import os

from requests_ratelimiter import LimiterAdapter
from urllib3.util.retry import Retry
from urllib.parse import quote as urlize
from requests_cache import CachedSession

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

CACHE_EXPIRATION = 43200  # 12 hours. This is a personal preference. IA requests have no expiration headers. Longer expiry means larger cache. Shorter expiry means more disk operations.
CACHE_BACKEND = "sqlite"  # SQLite is the most efficient backend for requests_cache. It is also the most efficient for requests_ratelimiter. Memory backend is not recommended for requests_ratelimiter.
CACHE_CONTROL = (
    False  # As already mentioned, I discovered the default expiration to be Null.
)
MAX_RETRIES = 3  # Maximum number of retries before giving up on a particular item in search results. If abandoned, the item will not appear in search results. The higher you go, the slower your other results load due to rate-limit.
BACKOFF_FACTOR = 1  # The maximum I would risk before repeating a request. 3 successive retries (worst case) in 1, 2, and 4 seconds respectively.
RATE_LIMIT = 5  # Beyond this would be too much. 5 is high on API calls. 1 is too low. 3 is a good balance. Exceeding this could get you rate-limted or blocked.
RETRY_STATUS_CODES = [500, 502, 503, 504]  # Retrying on these specific server errors.
MAX_WORKERS = 32 # Maximum number of threads to use for fetching metadata. This is a personal preference. The higher you go, the more requests you make to the server. The lower you go, the slower your search results load. In event workers get tied up you want to have higher number of workers to keep the search results coming.
CACHE_NAME = os.path.join(os.environ["APP_DIR"], "librivox_cache.sqlite")
SELECTED_FORMAT = "128Kbps MP3" #"64Kbps MP3"  # original format of LibriVox collection, near CD quality. Other formats are available. Refer : https://archive.org/post/1053663/file-format

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class LibriVox(Driver):
    """
    Driver for LibriVox.
    Making use of the internetarchive metadata API to browse and fetch audiobooks
    while respecting rate limits.
    """

    site_url = "https://archive.org"
    downloader_factory = MP3Downloader

    
    session = CachedSession(
        cache_name=CACHE_NAME,
        cache_control=CACHE_CONTROL,
        backend=CACHE_BACKEND,
        expire_after=CACHE_EXPIRATION,
    )

    retries_adapter = Retry(
        total=MAX_RETRIES,
        backoff_factor=BACKOFF_FACTOR,
        status_forcelist=RETRY_STATUS_CODES,
        raise_on_status=False,
    )
    session.mount(site_url, retries_adapter)

    ratelimit_adapter = LimiterAdapter(per_second=RATE_LIMIT)
    session.mount(site_url, ratelimit_adapter)
    threading.Thread(
        target=session.cache.remove_expired_responses
    ).start()  # an opportunity to clear up expired cache




    def get_book(self, url: str) -> Book:
        """
        def get_book(self, url: str) -> Book:

        Fetches a book from Internet Archive using the identifier.

        This method uses the rate-limited class-method 'self.session' to fetch metadata for an archive.org audiobook, specifically from the Librivox collection. The URL of the audiobook is passed into this function.

        Args:
            url (str): The URL of the audiobook on archive.org. This URL is used to fetch metadata and chapter information for the audiobook.

        Returns:
           Book: A Book object containing metadata and chapter information for the audiobook.
        """
        threading.Thread(
            target=self.session.cache.remove_expired_responses
        ).start()  # an opportunity to clear up expired cache. Had to tie it to some event to save the bother of setting up a cron job.
        
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
        response = self.session.get(f"{self.site_url}/metadata/{identifier}")
        print(f"cached response for {identifier}?: {response.from_cache}")
        logger.debug(f"cached response for {identifier}?: {response.from_cache}")
        meta_item = response.json()

        if "metadata" in meta_item.keys():
            metadata = meta_item["metadata"]
            if "creator" in metadata.keys():
                author = metadata["creator"]
            if "title" in metadata.keys():
                title = metadata["title"]
            if "runtime" in metadata.keys():
                duration = hms_to_sec(metadata["runtime"])
            if "description" in metadata.keys():
                description = html_to_text(metadata["description"])
        if "files" in meta_item.keys():
            files = meta_item["files"]
            cover_filename = next(
                (item["name"] for item in files if item["format"] == "JPEG"),
                None,  # Only one cover file image is presetn per audiobook and only cover file image has format label JPEG. others have "JPEG thumb"
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
                file_url = (
                    f"{self.site_url}/download/{identifier}/{file['name']}"  # explicit
                )
            if "title" in keys:
                chapter_title = file["title"]
            if "title" in keys:
                chapter_title = file["title"]
            if "length" in keys:
                if (
                    file["format"] == "64Kbps MP3"
                ):  # special condition. lengthetadata for "64Kbps MP3" files is in hh:mm:ss format
                    end_time = hms_to_sec(file["length"])
                elif file["format"] == "128Kbps MP3":
                    end_time = floor(
                        float(file["length"])
                    )  # special condition metadata for "128Kbps MP3" files is in float format (seconds with decimal)

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
            series_name=None,
            number_in_series=None,
            description=description,
            reader="No Data", #This information is available on librivox.org but not in archive.org metadata- at least not for all items.
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=chapters,
        )

    def search_books(self, query: str, limit: int = 20, offset: int = 0) -> list[Book]:
        """
        def search_books(self, query: str, limit: int = 10, offset: int = 0) -> Book:

        """

        def fetch_item(identifier):
            """
            a sub-function to fetch a single book's metadata from the archive.org metadata API
            """
            threading.Thread(
                target=self.session.cache.remove_expired_responses
            ).start()  # an opportunity to clear up expired cache
            # logger.debug(f"Fetching book {identifier}")
            ia_bookObj = self.session.get(
                f"{self.site_url}/metadata/{identifier}"
            ).json()
            keys = ia_bookObj.keys()
            files, author, name, duration, cover_filename, coverImg, reader = (
                [],
                None,
                None,
                None,
                None,
                None,
                None,
            )
            keys = ia_bookObj.keys()
            if "metadata" in keys:
                metadata = ia_bookObj["metadata"]
                keys_2 = metadata.keys()
                if "creator" in keys_2:
                    author = metadata["creator"]
                if "title" in keys_2:
                    name = metadata["title"]
                if "runtime" in keys_2:
                    duration = metadata[
                        "runtime" 
                    ] #runtime is expected to be formatted as it is. This is headed to the search preview templat.
                if "reader" in keys:
                    reader = metadata["reader"]
            else:
                logger.debug(f"No metadata found for {identifier}")
            if "files" in keys:
                files = ia_bookObj["files"]
            cover_filename = next(
                (item["name"] for item in files if item["format"] == "JPEG"), None
            )
            if cover_filename != None:
                coverImg = f"{self.site_url}/download/{identifier}/{cover_filename}"

            return Book(
                author=safe_name(author),
                name=safe_name(name),
                duration=duration,
                url=f"{self.site_url}/details/{identifier}",
                preview=coverImg if coverImg else "No Data",
                driver=self.driver_name,
                reader=reader if reader else "No Data",
            )

        def fetch_items(identifiers):
            """
            def fetch_items(identifiers): -> list[Book]

            """
            books = []
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
                futures = {
                    executor.submit(fetch_item, identifier): identifier
                    for identifier in identifiers
                }
                for future in as_completed(futures):
                    try:
                        identifier = futures[future]
                        books.append(future.result())
                    except Exception as e:
                        logger.error(f"Error fetching book {identifier}: {e}")

            return books



        page = offset + 1
        books = []
        url_encoded=urlize(f'title:({query}) AND collection:"librivoxaudio"')
        result = self.session.get(
        
            f"https://archive.org/advancedsearch.php?q={url_encoded}&fl[]=identifier&sort[]=&sort[]=&sort[]=&rows={limit}&page={page}&output=json"
        ).json()
        if "response" in result.keys():
            result = result["response"]["docs"]
        else:
            return []
        hits = []
        if len(result) > 0:
            hits = [i["identifier"] for i in result]
        else:
            return []
        books = fetch_items(hits)
        return books

    def get_book_series(self, url: str) -> ty.List[Book]:
        """
        to be implemented
        Yet to find connecting pattern between books in a series in the collection.
        This is a placeholder because without it the class cannot be instantiated.
        """
        books = ty.List()
        return books

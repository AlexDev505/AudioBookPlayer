import typing as ty
from models.book import Book, BookItems, BookItem
from .base import Driver
from .downloaders import MP3Downloader
from .tools import safe_name, hms2sec, html2text
from requests import Session
import requests_ratelimiter
from urllib.parse import quote as urlize
import requests_cache
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

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
    adapter = requests_ratelimiter.LimiterAdapter(per_second=5)
    session = Session()
    session.mount(site_url, adapter)
    requests_cache.install_cache(
        "librivox_cache", backend="memory", expire_after=600
    )  # cache set for 10 minutes- enough to add it to library. Using memory right now. Plan to try sqlite (in-memory and/or disk)


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
        meta_item = self.session.get(f"{self.site_url}/metadata/{identifier}").json()
        logger.debug(f"Cache hit: {meta_item.from_cache}")
        if "metadata" in meta_item.keys():
            metadata = meta_item["metadata"]
            if "creator" in metadata.keys():
                author = metadata["creator"]
            if "title" in metadata.keys():
                title = metadata["title"]
            if "runtime" in metadata.keys():
                duration = metadata["runtime"]
            if "description" in metadata.keys():
                description = html2text(metadata["description"])
        if "files" in meta_item.keys():
            files = meta_item["files"]
            cover_filename = next(
                (item["name"] for item in files if item["format"] == "JPEG"), None
            )
            preview = (
                f"{self.site_url}/download/{identifier}/{cover_filename}"
                if cover_filename
                else "No Data"
            )

        chapters = BookItems()
        audiofiles = [file for file in files if file["format"] == "64Kbps MP3"]
        for file in audiofiles:
            file_url, file_index, title, start_time, end_time = (
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
                title = file["title"]
            if "length" in keys:
                end_time = hms2sec(file["length"])
            chapters.append(
                BookItem(
                    file_url="No Data" if len(file_url) == 0 else file_url,
                    file_index=file_index,
                    title="No Data" if len(title) == 0 else title,
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
            reader="No Data",
            duration=duration,
            url=url,
            preview=preview,
            driver=self.driver_name,
            items=chapters,
        )

    def search_books(self, query: str, limit: int = 10, offset: int = 0) -> list[Book]:
        """
        def search_books(self, query: str, limit: int = 10, offset: int = 0) -> Book:

        """

        def fetch_item(identifier):
            logger.debug(f"Fetching book {identifier}")
            ia_bookObj = self.session.get(
                f"{self.site_url}/metadata/{identifier}"
            ).json()
            keys = ia_bookObj.keys()
            files, author, name, duration, cover_filename, coverImg = (
                [],
                None,
                None,
                None,
                None,
                None,
            )
            if "metadata" in keys:
                if "creator" in ia_bookObj["metadata"].keys():
                    author = ia_bookObj["metadata"]["creator"]
                if "title" in ia_bookObj["metadata"].keys():
                    name = ia_bookObj["metadata"]["title"]
                if "runtime" in ia_bookObj["metadata"].keys():
                    duration = ia_bookObj["metadata"]["runtime"]
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
            )

        def fetch_items(identifiers):
            """
            def fetch_items(identifiers): -> list[Book]

            """
            books = []
            with ThreadPoolExecutor(max_workers=7) as executor:
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
        result = self.session.get(
            f"https://archive.org/advancedsearch.php?q={urlize('title:('+query+')')}+AND+collection:%22librivoxaudio%22&fl[]=identifier&sort[]=&sort[]=&sort[]=&rows={limit}&page={page}&output=json"
        ).json()["response"]["docs"]
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
        """
        books = ty.List()
        return books

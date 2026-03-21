from __future__ import annotations

import os
import typing as ty
from abc import ABC, abstractmethod
from contextlib import suppress
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from functools import wraps
from hashlib import md5
from pathlib import Path
from urllib.parse import urlparse

from aiodbcore.models import Field, Index

from tools import normalize_author, normalize_string

# Will be used for datetime formatting in UI
DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class BookStatus(Enum):
    NEW = "new"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class ListeningProgress:
    chapter_index: int = 0
    time: int = 0


@dataclass
class Chapter:
    title: str
    url: str
    file_index: int
    start_time: int
    end_time: int

    @property
    def duration(self) -> int:
        return self.end_time - self.start_time

    def __repr__(self) -> str:
        return f"<Chapter {self.title}>"


class Chapters(list[Chapter]):
    def __init__(self, iterable: ty.Iterable[dict]):
        super().__init__(Chapter(**kwargs) for kwargs in iterable)


@dataclass(kw_only=True)
class BookSource(ABC):
    id: Field[int] = Field(-1)
    related_book: ty.Annotated[Field[int], Index("related_book_id")] = Field(-1)
    url: ty.Annotated[Field[str], Index("source_url", unique=True)]
    cover: Field[str]

    selected: Field[bool] = Field(False)
    status: Field[BookStatus] = Field(BookStatus.NEW)
    files: Field[dict[str, str]] = Field(field(default_factory=dict))
    """ Dict like {file_name: hash} """

    @property
    @abstractmethod
    def progress_percent(self) -> int:
        pass

    @property
    @abstractmethod
    def dir_path(self) -> Path:
        pass

    @property
    def cover_path(self) -> Path:
        return self.dir_path / "cover.jpg"

    @property
    def is_downloaded(self) -> bool:
        return bool(self.files)

    @property
    def domain(self) -> str:
        return urlparse(self.url).netloc.split(".")[0]

    def asdict(self) -> dict[str, ty.Any]:
        return dict(
            sid=str(SourceId.from_source(self)),
            url=self.url,
            domain=self.domain,
            cover=self.cover,
            local_cover=str(self.cover_path),
            selected=self.selected,
            status=self.status.value,
            progress_percent=self.progress_percent,
            downloaded=self.is_downloaded,
            files=list(self.files.keys()),
        )

    def __repr__(self):
        return f"{self.__class__.__name__}(id={self.id}, url={self.url})"

    def __format__(self, format_spec):
        if format_spec == "colored":
            return (
                f"<g>{self.__class__.__name__}</g><w>("
                f"<le>id</le>=<y>{self.id}</y>, "
                f"<le>url</le>=<y>{self.url}</y>)</w>"
            )
        return repr(self)


@dataclass(kw_only=True)
class TextBook(BookSource):
    publication: Field[str]
    file_url: Field[str]
    progress_percent: Field[int] = Field(0)  # type: ignore
    progress: Field[str] = Field("")

    @property
    def dir_path(self) -> Path:
        return Path(".")

    def asdict(self):
        res = super().asdict()
        res.update(
            dict(
                publication=self.publication,
                file_url=self.file_url,
                progress=self.progress,
            )
        )
        return res


@dataclass(kw_only=True)
class AudioBook(BookSource):
    narrator: Field[str]
    duration: Field[str]
    chapters: Field[Chapters]
    progress: Field[ListeningProgress] = Field(
        field(default_factory=ListeningProgress)
    )

    @property
    def progress_percent(self) -> int:
        if self.status == BookStatus.COMPLETED:
            return 100
        total = sum(chapter.duration for chapter in self.chapters)
        if not total:
            return 0
        cur = (
            sum(
                [
                    chapter.duration
                    for i, chapter in enumerate(self.chapters)
                    if i < self.progress.chapter_index
                ]
            )
            + self.progress.time
        )
        return int(round(cur / total * 100))

    @property
    def dir_path(self) -> Path:
        return Path(".", self.narrator)

    def asdict(self):
        res = super().asdict()
        res.update(
            dict(
                narrator=self.narrator,
                duration=self.duration,
                progress=asdict(self.progress),
                chapters=[asdict(chapter) for chapter in self.chapters],
            )
        )
        return res


class SourceType(Enum):
    AudioBook = AudioBook
    TextBook = TextBook


@dataclass
class SourceId[T: BookSource]:
    sid: int
    stype: ty.Type[T]

    @classmethod
    def from_source(cls, source: T) -> SourceId[T]:
        return cls(source.id, source.__class__)

    @classmethod
    def from_str(cls, s: str) -> SourceId | None:
        with suppress(ValueError, KeyError):
            stype, sid = s.split("-")
            return cls(int(sid), ty.cast(ty.Type[T], SourceType[stype].value))

    @classmethod
    def convert_param[SELF, **P, R](
        cls, func: ty.Callable[ty.Concatenate[SELF, SourceId, P], R]
    ) -> ty.Callable[ty.Concatenate[SELF, str, P], R]:
        @wraps(func)
        def _wrapper(
            self: SELF, sid: str, *args: P.args, **kwargs: P.kwargs
        ) -> R:
            if not (source_id := cls.from_str(sid)):
                raise ValueError(f"Invalid source id: {source_id}")
            return func(self, source_id, *args, **kwargs)

        return _wrapper

    def __hash__(self):
        return hash(str(self))

    def __repr__(self) -> str:
        return f"{self.stype.__name__}-{self.sid}"

    __str__ = __repr__


@dataclass(kw_only=True)
class BookData:
    title: Field[str]
    author: Field[str]
    series_name: Field[str]
    number_in_series: Field[str]
    description: Field[str]
    hash: ty.Annotated[Field[str], Index("book_hash", unique=True)] = Field("")

    def __post_init__(self):
        self.hash = md5(
            f"{normalize_string(self.title)} {normalize_author(self.author)}".encode()
        ).hexdigest()

    def asdict(self) -> dict[str, ty.Any]:
        return dict(
            title=self.title,
            author=self.author,
            series_name=self.series_name,
            number_in_series=self.number_in_series,
            description=self.description,
            hash=self.hash,
        )

    @property
    def book_path(self) -> Path:
        """
        :returns: Relative path to the book in the library
        """
        path = Path(".", self.author)
        if self.series_name:
            book_name = (
                f"{str(self.number_in_series).rjust(2, '0')}. {self.title}"
            )
            path /= self.series_name
            path /= book_name
        else:
            path /= self.title
        return path

    @property
    def dir_path(self) -> Path:
        """
        :returns: Absolute path to the directory where the book is stored
        """
        return Path(os.environ["books_folder"], self.book_path).absolute()

    @property
    def cover_path(self) -> Path:
        """
        :returns: Absolute path to the book cover file
        """
        return self.dir_path / "cover.jpg"


@dataclass(kw_only=True)
class BookPreview(BookData):
    urls: set[str]
    cover: str
    narrators: set[str]
    publications: set[str]
    durations: set[str]

    _updated: bool = False

    def asdict(self):
        res = super().asdict()
        res.update(
            cover=self.cover,
            urls=list(self.urls),
            narrators=list(self.narrators),
            publications=list(self.publications),
            durations=list(self.durations),
            updated=self.updated,
        )
        return res

    @property
    def updated(self) -> bool:
        if self._updated:
            self._updated = False
            return True
        return False

    def extend(self, other: BookPreview) -> None:
        self.urls.update(other.urls)
        self.narrators.update(other.narrators)
        self.publications.update(other.publications)
        self.durations.update(other.durations)
        self._updated = True


@dataclass(kw_only=True)
class RawBook[SourceT: BookSource](BookData):
    source: SourceT

    @property
    def dir_path(self) -> Path:
        return super().dir_path / self.source.dir_path

    def to_preview(self) -> BookPreview:
        narrators, publications, durations = set(), set(), set()
        if isinstance(self.source, AudioBook):
            if self.source.narrator:
                narrators.add(self.source.narrator)
            if self.source.duration:
                durations.add(self.source.duration)
        elif isinstance(self.source, TextBook):
            if self.source.publication:
                publications.add(self.source.publication)
        return BookPreview(
            title=self.title,
            author=self.author,
            series_name=self.series_name,
            number_in_series=self.number_in_series,
            description=self.description,
            urls={self.source.url},
            cover=self.source.cover,
            narrators=narrators,
            publications=publications,
            durations=durations,
        )

    def __repr__(self):
        return f"RawBook(title={self.title}, source={self.source})"

    def __format__(self, format_spec):
        if format_spec == "colored":
            return (
                f"<g>RawBook</g><w>("
                f"<le>title</le>=<y>{self.title}</y>, "
                f"<le>source</le>={self.source:colored})</w>"
            )
        return repr(self)


@dataclass(kw_only=True)
class Book(BookData):
    id: Field[int] = Field(-1)
    cover: Field[str]
    adding_date: Field[datetime] = Field(field(default_factory=datetime.now))
    favorite: Field[bool] = Field(False)
    status: Field[BookStatus] = Field(BookStatus.NEW)

    _text_sources: list[TextBook] = field(default_factory=list)
    _audio_sources: list[AudioBook] = field(default_factory=list)

    def iter_sources(self) -> ty.Generator[BookSource]:
        yield from self._text_sources
        yield from self._audio_sources

    def add_text_sources(self, *sources: TextBook) -> None:
        self._text_sources.extend(sources)

    def add_audio_sources(self, *sources: AudioBook) -> None:
        self._audio_sources.extend(sources)

    def to_raw_book[T: BookSource](self, source: T) -> RawBook[T]:
        return RawBook(
            title=self.title,
            author=self.author,
            series_name=self.series_name,
            number_in_series=self.number_in_series,
            description=self.description,
            source=source,
        )

    @classmethod
    def from_book_preview(cls, preview: BookPreview) -> Book:
        return cls(
            title=preview.title,
            author=preview.author,
            series_name=preview.series_name,
            number_in_series=preview.number_in_series,
            description=preview.description,
            cover=preview.cover,
        )

    def asdict(self, with_sources: bool = False) -> dict[str, ty.Any]:
        res = super().asdict()
        res.update(
            bid=self.id,
            cover=self.cover,
            local_cover=str(self.cover_path),
            dir_path=str(self.dir_path),
            adding_date=self.adding_date.strftime(DATETIME_FORMAT),
            favorite=self.favorite,
            status=self.status.value,
            audio_sources_count=len(self._audio_sources),
            text_sources_count=len(self._text_sources),
        )
        if with_sources:
            res.update(
                audio_sources=[
                    source.asdict() for source in self._audio_sources
                ],
                text_sources=[source.asdict() for source in self._text_sources],
            )
        return res

    def __repr__(self):
        return f"Book(id={self.id}, title={self.title})"

    def __format__(self, format_spec):
        if format_spec == "colored":
            return (
                f"<g>Book</g><w>("
                f"<le>id</le>=<y>{self.id}</y>, "
                f"<le>title</le>=<y>{self.title}</y>)</w>"
            )
        return repr(self)

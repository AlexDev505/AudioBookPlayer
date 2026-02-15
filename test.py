import re
from dataclasses import dataclass
from hashlib import md5


def normalize_string(string: str) -> str:
    return re.sub(r"[^\w\s]", "", string.lower())


def normalize_author(author: str) -> str:
    return " ".join(sorted(normalize_string(author).split()))


@dataclass(kw_only=True)
class BookData:
    title: str
    author: str
    series_name: str
    number_in_series: str
    description: str
    hash: str = ""

    def __post_init__(self):
        self.hash = md5(
            f"{normalize_string(self.title)} {normalize_author(self.author)}".encode()
        ).hexdigest()

    def __hash__(self):
        return hash(self.hash)

    def __eq__(self, other):
        if not isinstance(other, BookData):
            return False
        return self.hash == other.hash


@dataclass(kw_only=True)
class BookPreview(BookData):
    urls: set[str]
    cover: str
    narrators: set[str]
    publications: set[str]
    durations: set[str]

    _updated: bool = False

    def __hash__(self):
        print(self.hash)
        return super().__hash__()

    def __eq__(self, other):
        if not isinstance(other, BookData):
            return False
        return self.hash == other.hash

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


a = {}
c = BookPreview(
    title="Мать ученья",
    author="Domagoj Kurmaic aka nobody103",
    series_name="Series Name",
    number_in_series="Number in Series",
    description="Description",
    urls={"url2"},
    cover="cover.jpg",
    narrators={"Narrator 2"},
    publications={"Publication 2"},
    durations={"Duration 2"},
)
d = BookPreview(
    title="Title",
    author="Author",
    series_name="Series Name",
    number_in_series="Number in Series",
    description="Description",
    urls={"url1"},
    cover="cover.jpg",
    narrators={"Narrator 1"},
    publications={"Publication 1"},
    durations={"Duration 1"},
)

a[c] = c
print(a[c])
print(a[d])

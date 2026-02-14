import typing as ty


class JSApiError(Exception):
    code: int = 1
    msg: str = ""
    """ Message for UI """
    explain: str = "{msg}"
    """ Message for console and log file """

    def __init__(
        self,
        msg: str | None = None,
        explain: str | None = None,
        base_exc: Exception | None = None,
        **extra: ty.Any,
    ):
        self.msg = msg or self.msg
        self.explain = (explain or self.explain).format(**extra, msg=self.msg)
        self.base_exc = base_exc
        if base_exc:
            self.explain += f" {type(base_exc).__name__}: {base_exc}"
        self.extra = extra

    def __str__(self) -> str:
        return f"[{self.code}] {type(self).__name__}: {self.explain}"

    def __repr__(self) -> str:
        return self.msg

    def as_dict(self) -> dict:
        return dict(code=self.code, msg=self.msg, extra=self.extra)


class ConnectionFailedError(JSApiError):
    code = 2
    msg = _("connection_issues")
    explain = "Connection issues"


class BookAlreadyAdded(JSApiError):
    code = 3
    message = _("book.already_exists")
    explain = "Book already added to library"


class BookNotFound(JSApiError):
    code = 4
    message = _("book.not_found")


class BookAlreadyDownloaded(JSApiError):
    code = 5
    message = _("book.already_downloaded")


class BookNotDownloaded(JSApiError):
    code = 6
    message = _("book.not_downloaded")


class WaitForDownloadingEnd(JSApiError):
    code = 9
    message = _("book.wait_for_similar_book_downloading")


class NotAuthenticated(JSApiError):
    code = 10
    message = _("driver.not_authenticated")
    explain = "Driver {driver} not authenticated"

    def __init__(self, driver: str):
        super().__init__(driver=driver)


class NoSuitableDriver(JSApiError):
    code = 11
    message = _("no_suitable_driver")
    explain = "No suitable driver found for {book_url}"

    def __init__(self, book_url: str):
        super().__init__(book_url=book_url)

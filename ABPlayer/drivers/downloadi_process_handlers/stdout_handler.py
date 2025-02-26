import sys

from ..base import BaseDownloadProcessHandler


class StdoutDownloadProcessHandler(BaseDownloadProcessHandler):
    """
    Download process handler.
    Visualizes the book download process in the console.
    """

    def show_progress(self) -> None:
        sys.stdout.write(
            f"\r{self.status.value}: {self.done_size}/{self.total_size}\t"
            f"{round(self.done_size / (self.total_size / 100), 2)} %"
        )
        sys.stdout.flush()


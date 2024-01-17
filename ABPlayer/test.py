import sys
import os

os.environ["books_folder"] = r"E:\books"

from drivers import KnigaVUhe, BaseDownloadProcessHandler


class StdioDownloadProcessHandler(BaseDownloadProcessHandler):
    def show_progress(self) -> None:
        sys.stdout.write(
            f"\r{self.done_size}/{self.total_size}\t"
            f"{round(self.done_size / (self.total_size / 100), 2)} %"
        )
        sys.stdout.flush()


driver = KnigaVUhe()
driver.download_book(
    driver.get_book("https://knigavuhe.org/book/my-3/"), StdioDownloadProcessHandler()
)

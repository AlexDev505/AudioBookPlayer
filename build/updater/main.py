import os
import sys

os.environ["APP_DIR"] = os.path.join(os.environ["LOCALAPPDATA"], "AudioBookPlayer")
os.environ["DB_PATH"] = os.path.join(os.environ["APP_DIR"], "database.sqlite")
os.environ["DEFAULT_BOOKS_FOLDER"] = os.path.join(os.environ["APP_DIR"], "Книги")

if not os.path.exists(os.environ["DB_PATH"]):
    sys.exit()

from PyQt5.QtWidgets import QApplication  # noqa
from update_window import UpdateWindow  # noqa


def UpdateApp():
    """
    Инициализирует окно загрузки.
    """
    window = UpdateWindow()
    window.finished.connect(window.close)
    return window


def main():
    app = QApplication([])
    window = UpdateApp()
    window.show()
    app.exec()


if __name__ == "__main__":
    main()

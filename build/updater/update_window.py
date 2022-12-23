from __future__ import annotations

import datetime
import os
import pathlib
import shutil
import typing as ty
from contextlib import suppress

import msgspec
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor, QMovie
from PyQt5.QtWidgets import QGraphicsDropShadowEffect, QMainWindow

import window_geometry
from database import Books, Config
from drivers import drivers, chromedriver
from tools import BaseWorker
from ui.update_window import UiUpdateWindow

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore


class UpdateWindow(QMainWindow, UiUpdateWindow):
    finished: QtCore.pyqtBoundSignal = pyqtSignal()

    def __init__(self):
        super(UpdateWindow, self).__init__()
        self.setupUi(self)

        # Окно без рамки
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowMinimizeButtonHint)
        self.setAttribute(Qt.WA_TranslucentBackground)

        # Тень вокруг окна
        self.setAttribute(Qt.WA_TranslucentBackground)
        # Оставляем область вокруг окна, в котором будет отображена тень
        self.centralwidget.layout().setContentsMargins(15, 15, 15, 15)
        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(15)  # Размытие
        self.shadow.setColor(QColor(0, 0, 0, 100))
        self.shadow.setOffset(0)  # Смещение
        self.centralwidget.setGraphicsEffect(self.shadow)

        # Анимация загрузки
        self.loading_movie = QMovie(":/other/loading_app.gif")
        self.loading.setMovie(self.loading_movie)
        self.loading_movie.start()

        self.setupSignals()

        # Создаём новый поток для обновления
        self.worker = UpdateWorker(self)
        self.worker.start()

    def setupSignals(self):
        # Подготавливаем область, отвечающую за перемещение окна
        window_geometry.prepareDragZone(self, self.centralwidget)

    def workerChangeStatusHandler(self, text: str) -> None:
        """
        Обрабатывает изменения статуса обновления.
        :param text: Сообщение.
        """
        self.setStatus(text)

    def setStatus(self, text: str) -> None:
        """
        Изменяет текст статуса.
        """
        self.status.setText(text)
        self.status.setAlignment(Qt.AlignCenter)


class UpdateWorker(BaseWorker):
    status: QtCore.pyqtBoundSignal = pyqtSignal(str)
    finished: QtCore.pyqtBoundSignal = pyqtSignal()

    def __init__(self, update_window: UpdateWindow):
        super(UpdateWorker, self).__init__()
        self.update_window = update_window

    def connectSignals(self) -> None:
        self.status.connect(
            lambda text: self.update_window.workerChangeStatusHandler(text)
        )
        self.finished.connect(self.update_window.finished.emit)

    def worker(self) -> None:
        """
        Процесс обновления.
        Выполняется в отдельном потоке.
        """
        self.status.emit("Загрузка конфигурации")
        Config.init()
        self.status.emit("Проверка драйвера")
        chromedriver.install(signal=self.status)

        self.status.emit("Обновление формата библиотеки")

        book: Books
        with suppress(Exception):
            db = Books(os.environ["DB_PATH"])
            all_books = db.filter(return_list=True)
            with drivers[0](use_shared_browser=True):
                for i, book in enumerate(all_books):
                    self.status.emit(
                        f"Обновление формата библиотеки\t{i}/{len(all_books)}"
                    )
                    driver = [drv for drv in drivers if book.driver == drv.driver_name][
                        0
                    ](use_shared_browser=True)
                    new_book = driver.get_book(book.url)
                    data = dict(
                        author=new_book["author"],
                        name=new_book["name"],
                        series_name=new_book["series_name"],
                        number_in_series=new_book["number_in_series"],
                        description=new_book["description"],
                        reader=new_book["reader"],
                        duration=new_book["duration"],
                        url=new_book["url"],
                        preview=new_book["preview"],
                        driver=new_book["driver"],
                        items=new_book["items"],
                        status=book.status,
                        stop_flag=book.stop_flag,
                        favorite=book.favorite,
                        adding_date=datetime.datetime.now().strftime(
                            "%Y-%m-%d %H:%M:%S"
                        ),
                        files=book.files,
                    )
                    book_path = os.path.join(
                        os.environ["books_folder"], data["author"], data["name"]
                    )

                    if data["series_name"]:
                        new_book_path = pathlib.Path(
                            os.environ["books_folder"],
                            data["author"],
                            data["series_name"],
                            f"{data['number_in_series'].rjust(2, '0')}. {data['name']}",
                        )
                        if os.path.isdir(new_book_path):
                            pass
                        else:
                            if not os.path.isdir(book_path):
                                continue

                            files: list[str] = []
                            for _, _, files in os.walk(book_path):
                                break
                            if not files:
                                continue

                            new_book_path.mkdir(parents=True, exist_ok=True)
                            for file in files:
                                old_fp = os.path.join(book_path, file)
                                new_fp = os.path.join(new_book_path, file)
                                shutil.copyfile(old_fp, new_fp)
                                with suppress(Exception):
                                    os.remove(old_fp)

                            with suppress(Exception):
                                os.mkdir(book_path)

                        book_path = new_book_path

                    else:
                        if not os.path.isdir(book_path):
                            continue

                    file_path = os.path.join(book_path, ".abp")

                    with open(file_path, "wb") as file:
                        file.write(msgspec.json.encode(data))

            db.api.execute("DROP TABLE books")
            db.api.commit()

        self.status.emit("Готово")
        self.finished.emit()

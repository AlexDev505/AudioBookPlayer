from __future__ import annotations

import os
import ssl
import typing as ty
import urllib.request

import requests.exceptions
from PyQt5.QtCore import (
    QBasicTimer,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QSize,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QIcon, QMovie, QPixmap
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QToolTip,
    QVBoxLayout,
)

from database.tables.books import Books, Status
from drivers import BaseDownloadProcessHandler, drivers
from tools import BaseWorker, Cache, convert_into_bits
from .add_book_page import SearchWorker

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow
    from database.tables.books import Book

cache = Cache()


class DownloadPreviewWorker(BaseWorker):
    """
    Реализует скачивание обложки книги.
    При успешном скачивании обложка устанавливается в указанный QLabel.
    При ошибке скачивания указанный QLabel скрывается.
    """

    finished: QtCore.pyqtSignal = pyqtSignal(object)
    failed: QtCore.pyqtSignal = pyqtSignal()

    def __init__(
        self,
        main_window: MainWindow,
        cover_label: QLabel,
        size: ty.Tuple[int, int],
        book: Book,
    ):
        """
        :param cover_label: Экземпляр QLabel, для которого скачивается обложка.
        :param size: Размеры QLabel.
        :param book: Экземпляр книги.
        """
        super(DownloadPreviewWorker, self).__init__()
        self.main_window = main_window
        self.cover_label, self.size, self.book = cover_label, size, book

    def connectSignals(self) -> None:
        self.finished.connect(lambda pixmap: self.finish(pixmap))
        self.failed.connect(self.fail)

    def worker(self) -> None:
        try:
            pixmap = cache.get(self.book.preview)  # Проверяем кэш
            if not pixmap:
                if not self.book.preview:  # Если у книги нет обложки
                    raise ValueError
                # Скачивание
                context = ssl.SSLContext()
                data = urllib.request.urlopen(self.book.preview, context=context).read()
                pixmap = QPixmap()
                pixmap.loadFromData(data)
                cache.set(self.book.preview, pixmap)  # Заносим в кэш
            self.finished.emit(pixmap)
        except Exception:
            self.failed.emit()
        self.main_window.download_cover_thread_count -= 1

    def finish(self, pixmap: QPixmap) -> None:
        try:
            self.cover_label.setMovie(None)  # Отключаем анимацию загрузки
            if os.path.isdir(self.book.dir_path):  # Если книга скачана
                # Сохраняем обложку
                pixmap.save(os.path.join(self.book.dir_path, "cover.jpg"), "jpeg")
            # Подстраиваем размер обложки под QLabel
            pixmap = pixmap.scaled(*self.size, Qt.KeepAspectRatio)
            self.cover_label.setPixmap(pixmap)
        except RuntimeError:  # cover_label может быть удалён
            pass

    def fail(self) -> None:
        try:
            self.cover_label.setMovie(None)  # Отключаем анимацию загрузки
            self.cover_label.hide()  # Скрываем элемент
        except RuntimeError:  # cover_label может быть удалён
            pass


def loadPreview(
    main_window: MainWindow,
    cover_label: QLabel,
    size: ty.Tuple[int, int],
    book: Book,
) -> None:
    """
    Устанавливает обложку книги в определенный QLabel.
    Если обложка не скачана - скачивает.
    :param main_window: Экземпляр главного окна.
    :param cover_label: Экземпляр QLabel, для которого скачивается обложка.
    :param size: Размеры QLabel.
    :param book: Экземпляр книги.
    """
    try:
        cover_label.show()
    except RuntimeError:  # cover_label может быть удалён
        return

    cover_path = os.path.join(book.dir_path, "cover.jpg")
    if os.path.isfile(cover_path):  # Если обложка скачана
        pixmap = QPixmap()
        pixmap.load(cover_path)
        pixmap = pixmap.scaled(*size, Qt.KeepAspectRatio)
        cover_label.setPixmap(pixmap)
    else:
        # Анимация загрузки
        if not cover_label.movie():
            movie = QMovie(":/other/loading.gif")
            movie.setScaledSize(QSize(50, 50))
            cover_label.setMovie(movie)
            movie.start()

        # Запускаем максимум 2 потока для скачивания
        if main_window.download_cover_thread_count >= 2:
            QTimer.singleShot(
                2000, lambda: loadPreview(main_window, cover_label, size, book)
            )  # Пробуем запустить скачивание через 2 сек
            return

        # Создаем и запускаем новый поток
        main_window.download_cover_thread_count += 1
        cover_label.DownloadPreviewWorker = DownloadPreviewWorker(
            main_window, cover_label, size, book
        )
        cover_label.DownloadPreviewWorker.start()


class DownloadBookWorker(BaseWorker):
    """
    Реализует скачивание книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal()
    failed: QtCore.pyqtSignal = pyqtSignal(str)

    def __init__(self, main_window: MainWindow, book: Book):
        """
        :param main_window: Экземпляр главного окна.
        :param book: Экземпляр не скачанной книги.
        """
        super(DownloadBookWorker, self).__init__()
        self.main_window, self.book = main_window, book
        self.drv = [drv for drv in drivers if self.book.url.startswith(drv().site_url)][
            0
        ]()  # Драйвер, который нужно использовать для скачивания
        self.download_process_handler = DownloadProcessHandler(self.main_window)

    def connectSignals(self) -> None:
        self.finished.connect(self.finish)
        self.failed.connect(lambda text: self.fail(text))

    def worker(self) -> None:
        try:
            self.drv.download_book(self.book, self.download_process_handler)
            books = Books(os.environ["DB_PATH"])
            books.insert(**vars(self.book))  # Добавляем книгу в бд
            self.finished.emit()
        except requests.exceptions.ConnectionError:
            self.failed.emit(
                "Соединение с сервером потеряно.\n" "Проверьте интернет соединение."
            )
        except Exception as err:
            self.failed.emit(f"Ошибка при скачивании книги\n{str(err)}")
        self.main_window.downloadable_book = ...

    def finish(self) -> None:
        # Если пользователь находится на странице скачиваемой книги
        if self.main_window.pbFrame.minimumWidth() == 0:
            self.main_window.openBookPage(self.book)  # Обновляем страницу
        else:
            # Закрываем полосу прогресса
            if not self.main_window.__dict__.get("pb_animation"):
                self.main_window.pb_animation = QPropertyAnimation(
                    self.main_window.pbFrame, b"minimumWidth"
                )
                self.main_window.pb_animation.setDuration(150)
                self.main_window.pb_animation.setStartValue(150)
                self.main_window.pb_animation.setEndValue(0)
                self.main_window.pb_animation.setEasingCurve(QEasingCurve.InOutQuart)
                self.main_window.pb_animation.finished.connect(
                    lambda: self.main_window.__dict__.__delitem__("pb_animation")
                )  # Удаляем анимацию
                self.main_window.pb_animation.start()
            if (
                self.main_window.stackedWidget.currentWidget()
                == self.main_window.libraryPage
            ):
                self.main_window.openLibraryPage()

    def fail(self, text: str) -> None:
        self.main_window.openInfoPage(
            text=text,
            btn_text="Вернуться в библиотеку",
            btn_function=lambda: self.main_window.stackedWidget.setCurrentWidget(
                self.main_window.libraryPage
            ),
        )

    def terminate(self) -> Book:
        file = self.drv.__dict__.get("_file")
        if file:
            file.close()

        downloadable_book = self.main_window.downloadable_book
        self.thread.setTerminationEnabled(True)
        self.thread.exit()
        self.thread.terminate()
        self.thread.wait()
        self.main_window.downloadable_book = ...
        return downloadable_book


class DownloadProcessHandler(QObject, BaseDownloadProcessHandler):
    move: QtCore.pyqtSignal = pyqtSignal()

    def __init__(self, main_window: MainWindow):
        """
        :param main_window: Экземпляр главного окна.
        """
        super(DownloadProcessHandler, self).__init__()
        self.main_window = main_window
        self._last_size = ""
        self.move.connect(self._show_progress)

    def show_progress(self) -> None:
        """
        Отправляет сингал для отображения прогресса.
        Если отображать прогресс в том же потоке, возникают неприятные баги.
        """
        self.move.emit()

    def _show_progress(self) -> None:
        """
        Отображение прогресса.
        """
        progress = int(round(self.done_size / (self.total_size / 100), 0))
        self.main_window.downloadingProgressBarLg.setValue(progress)
        self.main_window.downloadingProgressBar.setValue(progress)
        self.main_window.downloadingProgressBar.setToolTip(
            f"{convert_into_bits(self.done_size)} / {convert_into_bits(self.total_size)}",
        )  # Изменяем всплывающую подсказку


def prepareProgressBar(pb: QProgressBar) -> None:
    """
    Модификация полосы загрузки.
    Позволяет динамически изменять всплывающую подсказку.
    :param pb: Экземпляр QProgressBar.
    """

    class ToolTipUpdater(QObject):
        """
        Реализует динамическое изменение всплывающей подсказки.
        """

        def timerEvent(self, x) -> None:
            QToolTip.showText(pb.toolTipPos, pb.toolTip(), pb)

    class PBEventFilter(QObject):
        def eventFilter(self, obj: QObject, event: QEvent) -> bool:
            """
            Обработчик событий полосы загрузки.
            :param obj:
            :param event:
            """
            if event.type() == QEvent.ToolTip:  # Удержание курсора на объекте
                pb.toolTipPos = (
                    event.globalPos()
                )  # Позиция, где будет отображена подсказка
                pb.toolTipUpdater = ToolTipUpdater()
                pb.toolTipTimer = QBasicTimer()
                pb.toolTipTimer.start(100, pb.toolTipUpdater)  # Обновление подсказки
                return True
            elif event.type() == QEvent.Leave:  # Курсор покидает объект
                if pb.__dict__.get("toolTipPos"):
                    pb.toolTipTimer.stop()
                    pb.toolTipPos = None
                    QToolTip.hideText()  # Скрываем подсказку
            return False

    pb.toolTipPos = None
    pb.ef = PBEventFilter()
    pb.installEventFilter(pb.ef)


def downloadBook(main_window: MainWindow, book: Book) -> None:
    """
    Запускает скачивание книги.
    :param main_window: Экземпляр главного окна.
    :param book: Экземпляр книги.
    """
    if main_window.downloadable_book is not ...:
        QMessageBox.information(
            main_window,
            "Предупреждение",
            "Дождитесь окончания скачивания другой книги",
        )
        return

    main_window.downloadingProgressBarLg.setValue(0)
    main_window.downloadingProgressBar.setValue(0)

    main_window.playerContent.setCurrentWidget(main_window.downloadingPage)
    main_window.saveBtn.hide()
    main_window.downloadable_book = book

    # Создаем и запускаем новый поток
    main_window.DownloadBookWorker = DownloadBookWorker(main_window, book)
    main_window.DownloadBookWorker.start()


class DeleteBookWorker(BaseWorker):
    """
    Реализует удаление книги.
    """

    finished: QtCore.pyqtSignal = pyqtSignal()
    failed: QtCore.pyqtSignal = pyqtSignal(str)

    def __init__(self, main_window: MainWindow, book: ty.Union[Book, Books]):
        super(DeleteBookWorker, self).__init__()
        self.main_window, self.book = main_window, book

    def connectSignals(self) -> None:
        self.finished.connect(self.finish)
        self.failed.connect(lambda text: self.fail(text))

    def worker(self) -> None:
        self.main_window.setLock(True)
        try:
            # Удаление книги из бд
            if self.book.__dict__.get("id"):
                books = Books(os.environ["DB_PATH"])
                books.api.execute("""DELETE FROM books WHERE id=?""", self.book.id)
                books.api.commit()
            # Удаление файлов книги
            if os.path.isdir(self.book.dir_path):
                for root, dirs, files in os.walk(self.book.dir_path):
                    for file in files:
                        os.remove(os.path.join(root, file))
                    os.rmdir(root)
                # Удаляем папку автора, если она пуста
                author_dir = os.path.dirname(self.book.dir_path)
                if len(os.listdir(author_dir)) == 0:
                    os.rmdir(author_dir)
            self.finished.emit()
        except PermissionError:  # Файл занят другим процессом
            # TODO: Можно удалять такие файлы после закрытия приложения
            self.finished.emit()
        except Exception as err:
            self.failed.emit(f"Возникла ошибка во время удаления книги.\n{str(err)}")
        self.main_window.setLock(False)

    def finish(self) -> None:
        self.main_window.openLibraryPage()

    def fail(self, text: str) -> None:
        self.main_window.openInfoPage(
            text=text,
            btn_text="Вернуться в библиотеку",
            btn_function=lambda: self.main_window.stackedWidget.setCurrentWidget(
                self.main_window.libraryPage
            ),
        )


def stopBookDownloading(main_window: MainWindow) -> None:
    """
    Останавливает загрузку книги и запускает процесс её удаления.
    :param main_window: Экземпляр главного окна.
    """
    if (
        QMessageBox.question(
            main_window,
            "Подтвердите действие",
            "Вы действительно хотите прервать скачивание книги?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        != QMessageBox.Yes
    ):
        return

    # Останавливаем скачивание
    downloadable_book: Book = main_window.DownloadBookWorker.terminate()

    main_window.openLoadingPage()

    # Создаем и запускаем новый поток
    main_window.DeleteBookWorker = DeleteBookWorker(main_window, downloadable_book)
    main_window.DeleteBookWorker.start()


def deleteBook(main_window: MainWindow, book: Books = None) -> None:
    """
    Запускает удаление книги.
    :param main_window: Экземпляр главного окна.
    :param book: Экземпляр книги. (Если не передан используется main_window.book)
    """
    book = book or main_window.book

    # TODO: Удаление прослушиваемой книги
    if main_window.player.book is not ... and main_window.player.book.url == book.url:
        main_window.openInfoPage(
            text="Невозможно удалить книгу, пока вы её слушаете.\n"
            "Начните слушать другую книгу и повторите попытку.",
            btn_text="В библиотеку",
            btn_function=main_window.openLibraryPage,
        )
        return

    if (
        QMessageBox.question(
            main_window,
            "Подтвердите действие",
            "Вы действительно хотите удалить книгу из библиотеки?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        != QMessageBox.Yes
    ):
        return

    main_window.openLoadingPage()

    # Создаем и запускаем новый поток
    main_window.DeleteBookWorker = DeleteBookWorker(main_window, book)
    QTimer.singleShot(2000, main_window.DeleteBookWorker.start)


def toggleFavorite(main_window: MainWindow, book: Books = None) -> None:
    """
    Добавляет/снимает метку "Избранное".
    Изменяет иконку кнопки.
    :param main_window: Экземпляр главного окна.
    :param book: Экземпляр книги. (Если не передан используется main_window.book)
    """
    book = book or main_window.book
    book.favorite = not book.favorite
    icon = QIcon(":/other/star_fill.svg" if book.favorite else ":/other/star.svg")
    main_window.sender().setIcon(icon)
    book.save()


class InputDialog(QDialog):
    """
    Диалоговое окно для получения ссылки на книгу.
    """

    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setWindowTitle("Изменение источника")

        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        self.buttonBox.accepted.connect(self.accept)
        self.buttonBox.rejected.connect(self.reject)

        self.layout = QVBoxLayout()
        self.message = QLabel("Введите ссылку на книгу")
        self.layout.addWidget(self.message)
        self.lineEdit = QLineEdit()
        self.layout.addWidget(self.lineEdit)
        self.layout.addWidget(self.buttonBox)
        self.setLayout(self.layout)

    def accept(self) -> None:
        """
        Нажатие на клавишу "ОК".
        """
        if self.lineEdit.text().strip():
            super(InputDialog, self).accept()
        else:
            self.lineEdit.setFocus()


def changeDriver(main_window: MainWindow) -> None:
    """
    Запускает изменение источника книги.
    :param main_window: Экземпляр главного окна.
    """

    def delete(book: Book) -> None:
        """
        Запускает удаление старой книги.
        :param book: Новая книга.
        """
        main_window.SearchWorker.deleteLater()

        # Создаем и запускаем новый поток для удаления старой книги
        main_window.DeleteBookWorker = DeleteBookWorker(main_window, main_window.book)
        # По завершению удаления, запускается скачивание
        main_window.DeleteBookWorker.finished.disconnect()
        main_window.DeleteBookWorker.finished.connect(lambda: download(book))
        main_window.DeleteBookWorker.start()

    def download(book: Book) -> None:
        """
        Запускает скачивание книги.
        :param book: Экземпляр книги.
        """
        main_window.DeleteBookWorker.deleteLater()
        main_window.openBookPage(book)

        main_window.downloadingProgressBarLg.setValue(0)
        main_window.downloadingProgressBar.setValue(0)

        main_window.playerContent.setCurrentWidget(main_window.downloadingPage)
        main_window.saveBtn.hide()
        main_window.downloadable_book = book

        # Создаем и запускаем новый поток для скачивания новой книги
        main_window.DownloadBookWorker = DownloadBookWorker(main_window, book)
        main_window.DownloadBookWorker.start()

    if main_window.downloadable_book is not ...:
        QMessageBox.information(
            main_window,
            "Предупреждение",
            "Дождитесь окончания скачивания другой книги",
        )
        return

    # TODO: Удаление прослушиваемой книги
    if (
        main_window.player.book is not ...
        and main_window.player.book.url == main_window.book.url
    ):
        main_window.openInfoPage(
            text="Невозможно удалить книгу, пока вы её слушаете.\n"
            "Начните слушать другую книгу и повторите попытку.",
            btn_text="В библиотеку",
            btn_function=main_window.openLibraryPage,
        )
        return

    # Создаём диалог и получаем ссылку
    dlg = InputDialog(main_window)
    url = _get_url(main_window, dlg)
    while not url:
        if url is False:  # Закрытие окна
            return
        url = _get_url(main_window, dlg)

    main_window.openLoadingPage()

    drv = [drv for drv in drivers if url.startswith(drv().site_url)][0]()

    # Создаём и запускаем новый поток для поиска книги
    main_window.SearchWorker = SearchWorker(main_window, drv, url)
    # По завершению поиска, запускается удаление старой книги
    main_window.SearchWorker.finished.disconnect()  # noqa
    main_window.SearchWorker.finished.connect(lambda book: delete(book))  # noqa
    main_window.SearchWorker.start()


def _get_url(main_window: MainWindow, dlg: InputDialog) -> ty.Union[None, False, str]:
    answer = dlg.exec()
    dlg.lineEdit.setFocus()
    url = dlg.lineEdit.text().strip()

    if not answer:  # Закрытие окна
        return False
    elif not any(url.startswith(drv().site_url) for drv in drivers):
        QMessageBox.critical(
            main_window, "Ошибка", "Драйвер для данного сайта не найден"
        )
    elif url == main_window.book.url:
        QMessageBox.information(
            main_window, "Внимание", "Ссылка ведёт на тот же источник"
        )
    else:
        return url


def listeningProgressTools(main_window: MainWindow) -> None:
    """
    Изменение прогресса по нажатию на кнопку.
    :param main_window: Экземпляр главного окна.
    """
    if main_window.book.status == Status.finished:
        answer = QMessageBox.question(
            main_window,
            "Подтвердите действие",
            "Пометить книгу как не прослушанное?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.No:
            return

        listening_progress = main_window.book.listening_progress
        if listening_progress == "0%":
            main_window.book.update(status=Status.new)
        else:
            main_window.book.update(status=Status.started)
        main_window.loadPlayer()
    else:
        answer = QMessageBox.question(
            main_window,
            "Подтвердите действие",
            "Пометить книгу как прослушанное?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )

        if answer == QMessageBox.No:
            return

        book = main_window.player.book
        if book is not ... and book.url == main_window.book.url:
            main_window.player.finish_book()
            main_window.loadPlayer()
        else:
            main_window.book.update(status=Status.finished)
            main_window.loadPlayer()

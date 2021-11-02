"""

Модификация метода изменения страницы.

"""

from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QTimer, QPropertyAnimation, QEasingCurve
from PyQt5.QtWidgets import QStackedWidget
from database.tables.books import Book

if ty.TYPE_CHECKING:
    from PyQt5.QtWidgets import QWidget
    from main_window import MainWindow


def setCurrentPage(main_window: MainWindow, page: QWidget) -> None:
    """
    Замена стандартному `stackedWidget.setCurrentPage`.

    Необходимо, потому что PyQt не успевает обновить
    минимальный размер `main_window.library`, из-за чего на других страницах
    нельзя уменьшить окно меньше чем, по факту возможно.

    Показывает/скрывает полосу загрузки на панели управления.

    :param main_window: Экземпляр главного окна.
    :param page: Новая страница.
    """
    # Скрытие / отображение полосы загрузки
    if not main_window.__dict__.get("pb_animation") and (
        main_window.downloadable_book is not ...
        or (main_window.downloadable_book is ... and main_window.pbFrame.width() != 0)
    ):
        main_window.pb_animation = QPropertyAnimation(
            main_window.pbFrame, b"minimumWidth"
        )
        main_window.pb_animation.setDuration(150)
        main_window.pb_animation.setEasingCurve(QEasingCurve.InOutQuart)
        main_window.pb_animation.finished.connect(
            lambda: main_window.__dict__.__delitem__("pb_animation")
        )  # Удаляем анимацию
        if main_window.pbFrame.width() != 0 and (
            main_window.downloadable_book is ...
            or (
                isinstance(main_window.downloadable_book, Book)
                and page == main_window.bookPage
                and main_window.book.url == main_window.downloadable_book.url
            )
        ):
            main_window.pb_animation.setStartValue(150)
            main_window.pb_animation.setEndValue(0)
            main_window.pb_animation.start()
        elif main_window.pbFrame.width() == 0:
            main_window.pb_animation.setStartValue(0)
            main_window.pb_animation.setEndValue(150)
            main_window.pb_animation.start()
        else:
            main_window.pb_animation.deleteLater()
            main_window.__dict__.__delitem__("pb_animation")

    if (
        main_window.stackedWidget.currentWidget() == main_window.libraryPage
        and page != main_window.libraryPage
    ):
        main_window.library.setMinimumWidth(0)
        QTimer.singleShot(
            100,
            lambda: QStackedWidget.setCurrentWidget(main_window.stackedWidget, page),
        )  # Меняем страницу через 1 миллисекунду
    else:
        QStackedWidget.setCurrentWidget(main_window.stackedWidget, page)

from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QTimer

if ty.TYPE_CHECKING:
    from PyQt5.QtWidgets import QWidget
    from main_window import MainWindow


def setCurrentPage(main_window: MainWindow, page: QWidget) -> None:
    """
    Замена стандартному `stackedWidget.setCurrentPage`.
    Необходимо, потому что PyQt не успевает обновить
    минимальный размер `main_window.library`, из-за чего на других страницах
    нельзя уменьшить окно меньше чем, по факту возможно.
    :param main_window: Экземпляр главного окна.
    :param page: Новая страница.
    """
    if main_window.stackedWidget.currentWidget() == main_window.libraryPage:
        main_window.library.setMinimumWidth(0)
        QTimer.singleShot(
            100, lambda: main_window.stackedWidget.oldSetCurrentWidget(page)
        )  # Меняем страницу через 1 миллисекунду
    else:
        main_window.stackedWidget.oldSetCurrentWidget(page)

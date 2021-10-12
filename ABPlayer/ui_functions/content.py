from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QTimer

if ty.TYPE_CHECKING:
    from PyQt5.QtWidgets import QWidget
    from main_window import MainWindow


def setCurrentPage(main_window: MainWindow, page: QWidget) -> None:
    if main_window.stackedWidget.currentWidget() == main_window.libraryPage:
        main_window.library.setMinimumWidth(0)
        QTimer.singleShot(
            100, lambda: main_window.stackedWidget.oldSetCurrentWidget(page)
        )
    else:
        main_window.stackedWidget.oldSetCurrentWidget(page)

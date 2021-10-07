from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QSize
from PyQt5.QtGui import QMovie
from drivers import drivers

if ty.TYPE_CHECKING:
    from main_window import MainWindow


def search(main_window: MainWindow) -> None:
    url = main_window.searchNewBookLineEdit.text()
    main_window.searchNewBookLineEdit.clear()
    if not url:
        main_window.searchNewBookLineEdit.setFocus()
        return

    main_window.openInfoPage(movie=_loading_animation(main_window))

    if not any(url.startswith(drv().site_url) for drv in drivers):
        main_window.openInfoPage(
            text="Драйвер для данного сайта не найден",
            btn_text="Вернуться",
            btn_function=lambda: main_window.stackedWidget.setCurrentWidget(
                main_window.addBookPage
            ),
        )


def _loading_animation(main_window: MainWindow) -> QMovie:
    main_window.movie = QMovie(":/other/loading.gif")
    main_window.movie.setScaledSize(QSize(50, 50))
    return main_window.movie

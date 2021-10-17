from __future__ import annotations

import typing as ty

from PyQt5.QtGui import QIcon, QPixmap

if ty.TYPE_CHECKING:
    from main_window import MainWindow


def resetAuthor(main_window: MainWindow) -> None:
    main_window.sortAuthor.setCurrentIndex(0)


def toggleInvertSort(main_window: MainWindow) -> None:
    # Изменяем иконку кнопки
    icon = QIcon()
    if main_window.invertSortBtn.isChecked():
        icon.addPixmap(QPixmap(":/other/sort_up.svg"), QIcon.Normal, QIcon.Off)
    else:
        icon.addPixmap(QPixmap(":/other/sort_down.svg"), QIcon.Normal, QIcon.Off)
    main_window.invertSortBtn.setIcon(icon)
    main_window.openLibraryPage()

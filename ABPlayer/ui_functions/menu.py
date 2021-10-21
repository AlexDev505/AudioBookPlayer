from __future__ import annotations

import os
import typing as ty

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap

if ty.TYPE_CHECKING:
    from PyQt5.QtWidgets import QPushButton
    from main_window import MainWindow


def toggleMenu(main_window: MainWindow) -> None:
    """
    Открывает/закрывает меню.
    :param main_window: Экземпляр главного окна.
    """
    if not main_window.__dict__.get("menu_animation"):
        width = main_window.menuFrame.width()  # Ширина меню сейчас
        # Конечная ширина меню. 200-открытое 65-закрытое
        end_value = 200 if width == 65 else 65

        main_window.menu_animation = QPropertyAnimation(
            main_window.menuFrame, b"minimumWidth"
        )
        main_window.menu_animation.setStartValue(width)
        main_window.menu_animation.setEndValue(end_value)
        main_window.menu_animation.setEasingCurve(QEasingCurve.InOutQuart)
        main_window.menu_animation.finished.connect(
            lambda: main_window.__dict__.__delitem__("menu_animation")
        )  # Удаляем анимацию
        main_window.menu_animation.start()

        # Изменяем иконку кнопки
        last_icon = main_window.menuBtn.__dict__.get("_last_icon")
        if not last_icon:
            last_icon = QIcon()
            last_icon.addPixmap(QPixmap(":/menu/menu.svg"), QIcon.Normal, QIcon.Off)

        main_window.menuBtn.__dict__["_last_icon"] = main_window.menuBtn.icon()
        main_window.menuBtn.setIcon(last_icon)


def buttonsHandler(main_window: MainWindow, button: QPushButton) -> None:
    """
    Обработчик кнопок меню.
    Открывает соответствующие страницы.
    :param main_window: Экземпляр главного окна.
    :param button: Нажатая кнопка.
    """
    if button == main_window.libraryBtn:
        main_window.favorite_books_page = False
        main_window.search_on = False
        main_window.openLibraryPage()
    elif button == main_window.favoriteBtn:
        main_window.favorite_books_page = True
        main_window.search_on = False
        main_window.openLibraryPage()
    elif button == main_window.addBookBtn:
        main_window.stackedWidget.setCurrentWidget(main_window.addBookPage)
        main_window.searchNewBookLineEdit.setFocus()
    elif button == main_window.settingsBtn:
        main_window.stackedWidget.setCurrentWidget(main_window.settingsPage)
    elif button == main_window.dirWithBooksBtn:
        os.startfile(os.environ["dir_with_books"])

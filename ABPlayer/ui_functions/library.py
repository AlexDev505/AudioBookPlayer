from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap

if ty.TYPE_CHECKING:
    from main_window import MainWindow


def toggleFiltersPanel(main_window: MainWindow) -> None:
    """
    Открывает/закрывает меню фильтров.
    :param main_window: Экземпляр главного окна.
    """
    if not main_window.__dict__.get("filters_menu_animation"):
        width = main_window.libraryFiltersPanel.width()  # Ширина меню сейчас
        # Конечная ширина меню 225-открытое 25-закрытое
        end_value = 225 if width == 25 else 25

        main_window.filters_menu_animation = QPropertyAnimation(
            main_window.libraryFiltersPanel, b"minimumWidth"
        )
        main_window.filters_menu_animation.setDuration(150)
        main_window.filters_menu_animation.setStartValue(width)
        main_window.filters_menu_animation.setEndValue(end_value)
        main_window.filters_menu_animation.setEasingCurve(QEasingCurve.InOutQuart)
        if end_value == 25:  # Скрываем содержимое
            main_window.filters_menu_animation.finished.connect(
                main_window.libraryFiltersFrame.hide
            )
        elif end_value == 225:
            main_window.libraryFiltersFrame.show()
        main_window.filters_menu_animation.finished.connect(
            lambda: main_window.__dict__.__delitem__("filters_menu_animation")
        )  # Удаляем анимацию
        main_window.filters_menu_animation.start()

        # Изменяем иконку кнопки
        last_icon = main_window.toggleBooksFilterPanelBtn.__dict__.get("_last_icon")
        if not last_icon:
            last_icon = QIcon()
            last_icon.addPixmap(
                QPixmap(":/other/angle_left.svg"), QIcon.Normal, QIcon.Off
            )

        main_window.toggleBooksFilterPanelBtn.__dict__[
            "_last_icon"
        ] = main_window.toggleBooksFilterPanelBtn.icon()
        main_window.toggleBooksFilterPanelBtn.setIcon(last_icon)

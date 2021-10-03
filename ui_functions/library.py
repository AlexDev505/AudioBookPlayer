from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap

if ty.TYPE_CHECKING:
    from main import Window


def toggleFiltersPanel(main_window: Window) -> None:
    """
    Открывает/закрывает меню фильтров.
    :param main_window: Инстанс окна.
    """

    def animation_finished() -> None:
        """
        Вызывается, после окончания анимации.
        """
        main_window.toggleBooksFilterPanelBtn.setDisabled(False)  # Включает кнопку
        if end_value == 25:
            main_window.libraryFiltersFrame.hide()

    width = main_window.libraryFiltersPanel.width()  # Ширина меню сейчас
    # Конечная ширина меню 225-открытое 25-закрытое
    end_value = 225 if width == 25 else 25

    # Отключаем кнопку на время анимации
    main_window.toggleBooksFilterPanelBtn.setDisabled(True)

    if end_value == 225:
        main_window.libraryFiltersFrame.show()

    main_window.filters_menu_animation = QPropertyAnimation(
        main_window.libraryFiltersPanel, b"minimumWidth"
    )
    main_window.filters_menu_animation.setDuration(150)
    main_window.filters_menu_animation.setStartValue(width)
    main_window.filters_menu_animation.setEndValue(end_value)
    main_window.filters_menu_animation.setEasingCurve(QEasingCurve.InOutQuart)
    main_window.filters_menu_animation.start()
    main_window.filters_menu_animation.finished.connect(animation_finished)

    # Изменяем иконку кнопки
    last_icon = main_window.toggleBooksFilterPanelBtn.__dict__.get("_last_icon")
    if not last_icon:
        last_icon = QIcon()
        last_icon.addPixmap(QPixmap(":/other/angle_left.svg"), QIcon.Normal, QIcon.Off)

    main_window.toggleBooksFilterPanelBtn.__dict__[
        "_last_icon"
    ] = main_window.toggleBooksFilterPanelBtn.icon()
    main_window.toggleBooksFilterPanelBtn.setIcon(last_icon)

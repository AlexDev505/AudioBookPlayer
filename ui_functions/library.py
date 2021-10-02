from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap

if ty.TYPE_CHECKING:
    from main import Window


def toggleFiltersPanel(main_window: Window) -> None:
    def animation_finished():
        main_window.toggleBooksFilterPanelBtn.setDisabled(False)
        if end_value == 25:
            main_window.libraryFiltersFrame.hide()

    width = main_window.libraryFiltersPanel.width()
    end_value = 225 if width == 25 else 25

    main_window.toggleBooksFilterPanelBtn.setDisabled(True)

    if end_value == 225:
        main_window.libraryFiltersFrame.show()

    main_window.animation = QPropertyAnimation(
        main_window.libraryFiltersPanel, b"minimumWidth"
    )
    main_window.animation.setDuration(500)
    main_window.animation.setStartValue(width)
    main_window.animation.setEndValue(end_value)
    main_window.animation.setEasingCurve(QEasingCurve.InOutQuart)
    main_window.animation.start()
    main_window.animation.finished.connect(
        animation_finished
    )  # Включаем кнопку по завершению анимации

    # Изменяем иконку кнопки
    last_icon = main_window.toggleBooksFilterPanelBtn.__dict__.get("_last_icon")
    if not last_icon:
        last_icon = QIcon()
        last_icon.addPixmap(QPixmap(":/other/angle_left.svg"), QIcon.Normal, QIcon.Off)

    main_window.toggleBooksFilterPanelBtn.__dict__[
        "_last_icon"
    ] = main_window.toggleBooksFilterPanelBtn.icon()
    main_window.toggleBooksFilterPanelBtn.setIcon(last_icon)

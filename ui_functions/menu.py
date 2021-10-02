from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap

if ty.TYPE_CHECKING:
    from main import Window


def toggleMenu(main_window: Window) -> None:
    width = main_window.menuFrame.width()
    end_value = 200 if width == 65 else 65

    main_window.menuBtn.setDisabled(True)
    main_window.animation = QPropertyAnimation(main_window.menuFrame, b"minimumWidth")
    main_window.animation.setDuration(250)
    main_window.animation.setStartValue(width)
    main_window.animation.setEndValue(end_value)
    main_window.animation.setEasingCurve(QEasingCurve.InOutQuart)
    main_window.animation.start()
    main_window.animation.finished.connect(
        lambda: main_window.menuBtn.setDisabled(False)
    )

    last_icon = main_window.menuBtn.__dict__.get("_last_icon")
    if not last_icon:
        last_icon = QIcon()
        last_icon.addPixmap(QPixmap(":/menu/menu.svg"), QIcon.Normal, QIcon.Off)

    main_window.menuBtn.__dict__["_last_icon"] = main_window.menuBtn.icon()
    main_window.menuBtn.setIcon(last_icon)
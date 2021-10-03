from __future__ import annotations

import typing as ty

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyle

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QEvent


def mousePressEvent(event: QEvent, sender, old_mouse_press_event) -> None:
    """
    Обрабатывает нажатие на слайдер.
    Реализует мгновенное изменения значения, при нажатии.
    :param event:
    :param sender: Отправитель события.
    :param old_mouse_press_event: Базовый обработчик события.
    """
    if event.button() == Qt.LeftButton:
        sender.setValue(
            QStyle.sliderValueFromPosition(
                sender.minimum(), sender.maximum(), event.x(), sender.width()
            )
        )
    old_mouse_press_event(event)

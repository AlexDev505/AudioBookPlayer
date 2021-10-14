from __future__ import annotations

import typing as ty

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyle

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QEvent
    from PyQt5.QtWidgets import QSlider, QWidget


def prepareSlider(slider: QSlider) -> None:
    slider.pressed = False
    slider.mousePressEvent = lambda e: mousePressEvent(e, slider)
    slider.mouseMoveEvent = lambda e: mouseMoveEvent(e, slider)
    slider.mouseReleaseEvent = lambda e: mouseReleaseEvent(e, slider)


def mousePressEvent(event: QEvent, sender) -> None:
    """
    Обрабатывает нажатие на слайдер.
    Реализует мгновенное изменения значения, при нажатии.
    :param event:
    :param sender: Отправитель события.
    """
    if event.button() == Qt.LeftButton:
        sender.pressed = True
        sender.setValue(
            QStyle.sliderValueFromPosition(
                sender.minimum(),
                sender.maximum(),
                event.x(),
                sender.width(),
            )
        )

    # sender.oldMousePressEvent(event)


def mouseReleaseEvent(event: QEvent, sender) -> None:
    if event.button() == Qt.LeftButton:
        sender.pressed = False
        sender.setValue(
            QStyle.sliderValueFromPosition(
                sender.minimum(),
                sender.maximum(),
                event.x(),
                sender.width(),
            )
        )


def mouseMoveEvent(event: QEvent, sender) -> None:
    """
    Обрабатывает движение мыши, с зажатой левой кнопкой, по слайдеру.
    Стандартный почему-то не всегда реагирует.
    :param event:
    :param sender: Отправитель события.
    """
    if sender.pressed:
        sender.setValue(
            QStyle.sliderValueFromPosition(
                sender.minimum(),
                sender.maximum(),
                event.x(),
                sender.width(),
            )
        )

"""

Модификации QSlider.

"""

from __future__ import annotations

import typing as ty

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QStyle

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import QEvent
    from PyQt5.QtWidgets import QSlider


def prepareSlider(slider: QSlider) -> None:
    """
    Изменение функциональности QSlider.
    :param slider: Экземпляр QSlider.
    """
    slider.pressed = False
    slider.mousePressEvent = lambda e: mousePressEvent(slider, e)
    slider.mouseMoveEvent = lambda e: mouseMoveEvent(slider, e)
    slider.mouseReleaseEvent = lambda e: mouseReleaseEvent(slider, e)


def mousePressEvent(slider: QSlider, event: QEvent) -> None:
    """
    Обрабатывает нажатие на слайдер.
    Реализует мгновенное изменения значения, при нажатии.
    :param slider: Отправитель события.
    :param event:
    """
    if event.button() == Qt.LeftButton:
        slider.pressed = True
        slider.setValue(
            QStyle.sliderValueFromPosition(
                slider.minimum(),
                slider.maximum(),
                event.x(),
                slider.width(),
            )
        )


def mouseReleaseEvent(slider, event: QEvent) -> None:
    """
    Обрабатывает отпускание кнопки мыши.
    :param slider: Отправитель события.
    :param event:
    """
    if event.button() == Qt.LeftButton:
        slider.pressed = False
        slider.setValue(
            QStyle.sliderValueFromPosition(
                slider.minimum(),
                slider.maximum(),
                event.x(),
                slider.width(),
            )
        )


def mouseMoveEvent(slider, event: QEvent) -> None:
    """
    Обрабатывает движение мыши, с зажатой левой кнопкой, по слайдеру.
    Стандартный почему-то не всегда реагирует.
    :param slider: Отправитель события.
    :param event:
    """
    if slider.pressed:
        slider.setValue(
            QStyle.sliderValueFromPosition(
                slider.minimum(),
                slider.maximum(),
                event.x(),
                slider.width(),
            )
        )

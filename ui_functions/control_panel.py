from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QPropertyAnimation, QEasingCurve
from PyQt5.QtGui import QIcon, QPixmap

if ty.TYPE_CHECKING:
    from PyQt5.QtWidgets import QPushButton
    from main import Window


def buttonsHandler(main_window: Window, button: QPushButton) -> None:
    """
    Обработчик кнопок панели управления.
    :param main_window: Инстанс окна.
    :param button: Нажатая кнопка.
    """
    if button == main_window.speedBtn:
        toggleSpeedSlider(main_window)
    elif button == main_window.volumeBtn:
        toggleVolumeSlider(main_window)


def toggleSpeedSlider(main_window: Window) -> None:
    """
    Показывает/скрывает регулятор скорости.
    :param main_window: Инстанс окна.
    """
    if main_window.volumeFrame.minimumWidth() != 0:
        toggleVolumeSlider(main_window)
    width = main_window.speedFrame.width()  # Ширина виджета сейчас
    # Конечная ширина виджета 110-открытое 65-закрытое
    end_value = 120 if width == 0 else 0

    main_window.speedBtn.setDisabled(True)  # Отключаем кнопку на время анимации
    main_window.speed_frame_animation = QPropertyAnimation(
        main_window.speedFrame, b"minimumWidth"
    )
    main_window.speed_frame_animation.setDuration(150)
    main_window.speed_frame_animation.setStartValue(width)
    main_window.speed_frame_animation.setEndValue(end_value)
    main_window.speed_frame_animation.setEasingCurve(QEasingCurve.InOutQuart)
    main_window.speed_frame_animation.start()
    main_window.speed_frame_animation.finished.connect(
        lambda: main_window.speedBtn.setDisabled(False)
    )  # Включаем кнопку по завершению анимации


def toggleVolumeSlider(main_window: Window) -> None:
    """
    Показывает/скрывает регулятор громкости.
    :param main_window: Инстанс окна.
    """
    if main_window.speedFrame.minimumWidth() != 0:
        toggleSpeedSlider(main_window)
    width = main_window.volumeFrame.width()  # Ширина виджета сейчас
    # Конечная ширина виджета 110-открытое 65-закрытое
    end_value = 120 if width == 0 else 0

    main_window.volumeBtn.setDisabled(True)  # Отключаем кнопку на время анимации
    main_window.volume_frame_animation = QPropertyAnimation(
        main_window.volumeFrame, b"minimumWidth"
    )
    main_window.volume_frame_animation.setDuration(150)
    main_window.volume_frame_animation.setStartValue(width)
    main_window.volume_frame_animation.setEndValue(end_value)
    main_window.volume_frame_animation.setEasingCurve(QEasingCurve.InOutQuart)
    main_window.volume_frame_animation.start()
    main_window.volume_frame_animation.finished.connect(
        lambda: main_window.volumeBtn.setDisabled(False)
    )  # Включаем кнопку по завершению анимации


def volumeSliderHandler(main_window: Window, value: int) -> None:
    """
    Обработчик изменений значения слайдера громкости.
    :param main_window: Инстанс окна.
    :param value: Новое значение.
    """
    main_window.volumeLabel.setText(f"{value} %")

    if value == 0:
        mute_icon = QIcon()
        mute_icon.addPixmap(QPixmap(":/volume/mute.svg"), QIcon.Normal, QIcon.Off)
        main_window.volumeBtn.setIcon(mute_icon)
    elif value < 33:
        low_volume_icon = QIcon()
        low_volume_icon.addPixmap(
            QPixmap(":/volume/low_volume.svg"), QIcon.Normal, QIcon.Off
        )
        main_window.volumeBtn.setIcon(low_volume_icon)
    elif 33 < value < 70:
        medium_volume_icon = QIcon()
        medium_volume_icon.addPixmap(
            QPixmap(":/volume/medium_volume.svg"), QIcon.Normal, QIcon.Off
        )
        main_window.volumeBtn.setIcon(medium_volume_icon)
    elif value > 70:
        volume_icon = QIcon()
        volume_icon.addPixmap(QPixmap(":/volume/volume.svg"), QIcon.Normal, QIcon.Off)
        main_window.volumeBtn.setIcon(volume_icon)


def speedSliderHandler(main_window: Window, value: int) -> None:
    """
    Обработчик изменений значения слайдера скорости.
    :param main_window: Инстанс окна.
    :param value: Новое значение.
    """
    if value == 50:
        value = 1
    else:
        value -= 50
        value *= 2
    value = value // 5 * 5
    main_window.speedLabel.setText(f"{'+' if abs(value) == value else ''}{value} %")
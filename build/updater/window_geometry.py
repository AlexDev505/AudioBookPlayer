"""

Функциональность, позволяющая изменять размеры окна, а так же перемещать его.

"""

from __future__ import annotations

import typing as ty

from PyQt5.QtCore import QEvent, QPoint, QRect, Qt
from loguru import logger

if ty.TYPE_CHECKING:
    from PyQt5.QtWidgets import QMainWindow, QWidget


def prepareDragZone(window: QMainWindow, obj: QWidget) -> None:
    """
    Подготавливает виджет, отвечающий за перемещение окна.
    :param window: Экземпляр окна.
    :param obj: Виджет.
    """
    obj.mousePressEvent = lambda e: dragZonePressEvent(window, e)
    obj.mouseMoveEvent = lambda e: dragZoneMoveEvent(window, e)
    obj.mouseReleaseEvent = lambda e: dragZoneReleaseEvent(window, e)


def dragZonePressEvent(window: QMainWindow, event: QEvent) -> None:
    """
    Обрабатывает нажатие на виджет, отвечающий за перемещение окна.
    :param window: Экземпляр окна.
    :param event:
    """
    if event.button() == Qt.LeftButton:
        window.__dict__["_drag_pos"] = event.globalPos()


def dragZoneMoveEvent(window: QMainWindow, event: QEvent) -> None:
    """
    Обрабатывает движение мыши по виджету, отвечающему за перемещение окна.
    :param window: Экземпляр окна.
    :param event:
    """
    if (
        window.__dict__.get("_drag_pos") is not None
        and window.cursor().shape() == Qt.ArrowCursor
    ):
        if window.isFullScreen():  # Выходим их полноэкранного режима
            screen_width = window.width()  # Ширина экрана
            toggleFullScreen(window)
            geometry = window.geometry()  # Размеры и положение окна

            window.setGeometry(
                (
                    event.globalPos().x()
                    - (geometry.width() * event.globalPos().x() / screen_width)
                ),  # Координата X
                event.globalPos().y(),  # Y
                geometry.width(),
                geometry.height(),
            )

        window.move(window.pos() + event.globalPos() - window.__dict__["_drag_pos"])
        window.__dict__["_drag_pos"] = event.globalPos()


def dragZoneReleaseEvent(window: QMainWindow, event: QEvent) -> None:
    """
    Обрабатывает отпускание кнопки мыши на виджете, отвечающем за перемещение окна.
    :param window: Экземпляр окна.
    :param event:
    """
    if event.button() == Qt.LeftButton:
        window.__dict__["_drag_pos"] = None


def mouseEvent(window: QMainWindow, event: QEvent) -> None:
    """
    Обрабатывает события мыши, для реализации изменения размера окна.
    :param window: Экземпляр окна.
    :param event:
    """
    if window.isFullScreen():
        return

    if event.type() == QEvent.HoverMove:  # Движение мыши по окну
        if window.__dict__.get("_start_cursor_pos") is None:
            _check_position(window, event)

    if event.type() == QEvent.MouseButtonPress:  # Нажатие
        if event.button() == Qt.LeftButton:
            window.__dict__["_start_cursor_pos"] = window.mapToGlobal(event.pos())
            window.__dict__["_start_window_geometry"] = window.geometry()

    elif event.type() == QEvent.MouseButtonRelease:  # Отпускание
        if event.button() == Qt.LeftButton:
            window.__dict__["_start_cursor_pos"] = None
            _check_position(window, event)

    elif event.type() == QEvent.MouseMove:  # Движение с зажатой кнопкой мыши
        if window.__dict__.get("_start_cursor_pos") is not None:
            if window.cursor().shape() in {Qt.SizeFDiagCursor}:
                _resize_window(window, event)


def _check_position(window: QMainWindow, event: QEvent) -> None:
    """
    Проверяет положение мыши.
    Устанавливает определённый курсор, при наведении на край и обратно.
    :param window: Экземпляр окна.
    :param event:
    """
    rect = window.rect()
    bottom_right = rect.bottomRight()

    if event.pos() in QRect(
        QPoint(bottom_right.x() - 30, bottom_right.y() - 30),
        QPoint(bottom_right.x(), bottom_right.y()),
    ):
        window.setCursor(Qt.SizeFDiagCursor)
    else:  # Обычный курсор
        if window.cursor() == Qt.SizeFDiagCursor:
            window.setCursor(Qt.ArrowCursor)


def _resize_window(window: QMainWindow, event: QEvent) -> None:
    """
    Изменяет размер окна.
    :param window: Экземпляр окна.
    :param event:
    """
    geometry = window.__dict__["_start_window_geometry"]
    last = window.mapToGlobal(event.pos()) - window.__dict__["_start_cursor_pos"]
    new_width = geometry.width() + last.x()
    new_height = geometry.height() + last.y()
    window.setGeometry(geometry.x(), geometry.y(), new_width, new_height)


def toggleFullScreen(window: QMainWindow) -> None:
    """
    Активирует/выключает полноэкранный режим.
    :param window: Экземпляр окна.
    """
    if not window.isFullScreen():
        logger.debug("Switch to full screen mode")
        # Скрываем место отведённое для тени
        window.centralWidget().layout().setContentsMargins(0, 0, 0, 0)
        window.showFullScreen()
        window.resizeWidgetFrame.hide()
    else:
        logger.debug("Exit full screen mode")
        # Отображаем место отведённое для тени
        window.centralWidget().layout().setContentsMargins(15, 15, 15, 15)
        window.showNormal()
        window.resizeWidgetFrame.show()

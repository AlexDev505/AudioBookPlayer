from __future__ import annotations

import typing as ty

from PyQt5.QtCore import Qt, QEvent, QRect, QPoint

if ty.TYPE_CHECKING:
    from main_window import MainWindow
    from PyQt5.QtWidgets import QMainWindow


def dragZonePressEvent(window: QMainWindow, event: QEvent) -> None:
    """
    Обрабатывает нажатие на виджет, отвечающий за перемещение окна.
    :param window: Инстанс окна.
    :param event:
    """
    if event.button() == Qt.LeftButton:
        window.__dict__["_drag_pos"] = event.globalPos()


def dragZoneMoveEvent(window: QMainWindow, event: QEvent) -> None:
    """
    Обрабатывает движение мыши по виджету, отвечающему за перемещение окна.
    :param window: Инстанс окна.
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
    :param window: Инстанс окна.
    :param event:
    """
    if event.button() == Qt.LeftButton:
        window.__dict__["_drag_pos"] = None


def mouseEvent(window: QMainWindow, event: QEvent) -> None:
    """
    Обрабатывает события мыши, для реализации изменения размера окна.
    :param window: Инстанс окна.
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
            if window.cursor().shape() in [Qt.SizeFDiagCursor]:
                _resize_window(window, event)


def _check_position(window: QMainWindow, event: QEvent) -> None:
    """
    Проверяет положение мыши.
    Устанавливает определённый курсор, при наведении на край и обратно.
    :param window: Инстанс окна.
    :param event:
    """
    rect = window.rect()
    bottom_right = rect.bottomRight()

    if event.pos() in QRect(
        QPoint(bottom_right.x(), bottom_right.y()),
        QPoint(bottom_right.x() - 10, bottom_right.y() - 10),
    ):
        window.setCursor(Qt.SizeFDiagCursor)
    else:  # Обычный курсор
        window.setCursor(Qt.ArrowCursor)


def _resize_window(window: QMainWindow, event: QEvent) -> None:
    """
    Изменяет размер окна.
    :param window: Инстанс окна.
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
    :param window: Инстанс окна.
    """
    if not window.isFullScreen():
        window.showFullScreen()
        window.resizeWidgetFrame.hide()
    else:
        window.showNormal()
        window.resizeWidgetFrame.show()

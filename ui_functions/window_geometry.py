from __future__ import annotations

import typing as ty

from PyQt5.QtCore import Qt, QEvent, QRect, QPoint

if ty.TYPE_CHECKING:
    from main import Window


def mousePressEvent(main_window: Window, event: QEvent) -> None:
    if event.button() == Qt.LeftButton:
        main_window.__dict__["_mouse_pos"] = event.globalPos()


def mouseMoveEvent(main_window: Window, event: QEvent) -> None:
    if main_window.cursor().shape() == Qt.ArrowCursor:
        if main_window.isFullScreen():
            screen_width = main_window.width()
            toggleFullScreen(main_window)
            geometry = main_window.geometry()

            main_window.setGeometry(
                event.globalPos().x()
                - (geometry.width() * event.globalPos().x() / screen_width),
                event.globalPos().y(),
                geometry.width(),
                geometry.height(),
            )

        main_window.move(
            main_window.pos() + event.globalPos() - main_window.__dict__["_mouse_pos"]
        )
        main_window.__dict__["_mouse_pos"] = event.globalPos()


def mouseEvent(main_window: Window, event: QEvent) -> None:
    if main_window.isFullScreen():
        return

    if event.type() == QEvent.HoverMove:
        if not main_window.__dict__.get("_is_pressed"):
            _check_position(main_window, event)

    elif event.type() == QEvent.MouseButtonPress:
        if event.button() == Qt.LeftButton:
            main_window.__dict__["_is_pressed"] = True
            main_window.__dict__["_start_cursor_pos"] = main_window.mapToGlobal(
                event.pos()
            )
            main_window.__dict__["_window_geometry"] = main_window.geometry()

    elif event.type() == QEvent.MouseButtonRelease:
        main_window.__dict__["_is_pressed"] = False
        _check_position(main_window, event)

    elif event.type() == QEvent.MouseMove:
        if main_window.cursor().shape() in [Qt.SizeFDiagCursor]:
            _resize_window(main_window, event)


def _check_position(main_window: Window, event: QEvent) -> None:
    rect = main_window.rect()
    bottom_right = rect.bottomRight()

    if event.pos() in QRect(
        QPoint(bottom_right.x(), bottom_right.y()),
        QPoint(bottom_right.x() - 5, bottom_right.y() - 5),
    ):
        main_window.setCursor(Qt.SizeFDiagCursor)
    else:  # to default
        main_window.setCursor(Qt.ArrowCursor)


def _resize_window(main_window: Window, event: QEvent) -> None:
    geometry = main_window.__dict__["_window_geometry"]
    last = (
        main_window.mapToGlobal(event.pos()) - main_window.__dict__["_start_cursor_pos"]
    )
    new_width = geometry.width() + last.x()
    new_height = geometry.height() + last.y()
    main_window.setGeometry(geometry.x(), geometry.y(), new_width, new_height)


def toggleFullScreen(main_window: Window) -> None:
    if not main_window.isFullScreen():
        main_window.showFullScreen()
        main_window.resizeWidgetFrame.hide()
    else:
        main_window.showNormal()
        main_window.resizeWidgetFrame.show()

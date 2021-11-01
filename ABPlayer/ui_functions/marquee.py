"""

Преобразование QLabel в marquee.
Marquee - Виджет, с автоматически прокручиваемым по горизонтали текстом.

"""

from __future__ import annotations

import re
import typing as ty

from PyQt5.QtCore import QEvent, QTimer
from PyQt5.QtGui import QFontMetrics, QPainter, QTextDocument
from PyQt5.QtWidgets import QLabel

if ty.TYPE_CHECKING:
    from main_window import MainWindow


def prepareLabel(main_window: MainWindow, label: QLabel) -> None:
    """
    Модифицирует QLabel, превращая его в marquee
    :param main_window: Экземпляр главного окна.
    :param label: Экземпляр QLabel.
    """
    label.marquee_state = False  # Превращен ли в marquee
    label.marquee = QTextDocument(label)
    label.marquee.setUseDesignMetrics(True)
    label.marquee.setDefaultFont(label.font())
    color = re.search(
        r"QWidget {\n {4}color: (?P<rgb>.+)\n}",
        main_window.centralwidget.styleSheet(),
        flags=re.MULTILINE,
    )
    label.styleSheet_ = f"color: {color.group('rgb')}" if color else ""
    label.timer = QTimer(label)
    label.timer.timeout.connect(lambda: _moveText(label))
    label.setText = lambda text: setText(label, text)
    label.paintEvent = lambda event: paintEvent(label, event)


def setText(label: QLabel, text: str) -> None:
    """
    Модифицирует QLabel.setText().
    :param label: Экземпляр QLabel.
    :param text: Новый текст.
    """
    QLabel.setText(label, text)
    fm = QFontMetrics(label.font())
    if fm.width(text) >= 180:  # Если текст большой
        label.marquee_state = True  # Превращаем QLabel в marquee
        label.setStyleSheet("color: rgba(0, 0, 0, 0)")
        label.x = 0
        label.marquee.setTextWidth(fm.width(text) * 1.06)
        html = f"""<html>
            <head><style>body {{{label.styleSheet_}}}</style></head>
            <body>{text}</body>
        </html>"""
        label.marquee.setHtml(html)
        label.timer.start(20)  # Запускаем таймер
    else:  # Оставляем QLabel таким же
        label.timer.stop()
        label.marquee_state = False
        label.setStyleSheet(label.styleSheet_)
        label.marquee.setHtml("")


def paintEvent(label: QLabel, event: QEvent) -> bool:
    """
    Отрисовка marquee.
    :param label: Экземпляр QLabel.
    :param event:
    """
    if label.__dict__.get("marquee_state"):
        p = QPainter(label)
        p.translate(label.x, -4)  # Изменяем положение текста
        label.marquee.drawContents(p)
    return QLabel.paintEvent(label, event)


def _moveText(label: QLabel) -> None:
    """
    Изменяет положение текста.
    :param label: Экземпляр QLabel.
    """
    if label.width() - label.x < label.marquee.textWidth():  # noqa
        label.x -= 1
    else:
        label.timer.stop()
        QTimer.singleShot(1000, lambda: _restart(label))
    label.repaint()


def _restart(label: QLabel) -> None:
    """
    Запускаем анимацию заново.
    :param label: Экземпляр QLabel.
    """
    label.x = 0
    label.repaint()
    label.timer.start(20)

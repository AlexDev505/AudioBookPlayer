from __future__ import annotations

import re
import typing as ty

from PyQt5.QtCore import QTimer, QEvent
from PyQt5.QtGui import QTextDocument, QPainter, QFontMetrics
from PyQt5.QtWidgets import QLabel

if ty.TYPE_CHECKING:
    from main_window import MainWindow


def prepareLabel(main_window: MainWindow, label: QLabel) -> None:
    label.marquee_state = False
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
    label.event = lambda event: eventFilter(label, event)
    label.paintEvent = lambda event: paintEvent(label, event)


def setText(label: QLabel, text: str) -> None:
    QLabel.setText(label, text)
    fm = QFontMetrics(label.font())
    if fm.width(text) >= 180:
        label.marquee_state = True
        label.setStyleSheet("color: rgba(0, 0, 0, 0)")
        label.x = 0
        label.paused = False
        label.marquee.setTextWidth(fm.width(text) * 1.06)
        html = f"""<html>
            <head><style>body {{{label.styleSheet_}}}</style></head>
            <body>{text}</body>
        </html>"""
        label.marquee.setHtml(html)
        label.timer.start(20)
    else:
        label.timer.stop()
        label.marquee_state = False
        label.setStyleSheet(label.styleSheet_)
        label.marquee.setHtml("")


def eventFilter(label: QLabel, event: QEvent) -> bool:
    print(event)
    if event.type() == QEvent.Enter:
        print("enter")
        label.paused = True
    elif event.type() == QEvent.Leave:
        print("leave")
        label.paused = False
    return QLabel.event(label, event)


def paintEvent(label: QLabel, event: QEvent) -> bool:
    if label.__dict__.get("marquee_state"):
        p = QPainter(label)
        p.translate(label.x, -4)
        label.marquee.drawContents(p)
    return QLabel.paintEvent(label, event)


def _moveText(label: QLabel) -> None:
    if not label.paused:
        if label.width() - label.x < label.marquee.textWidth():  # noqa
            label.x -= 1
        else:
            label.timer.stop()
            QTimer.singleShot(1000, lambda: _restart(label))
    label.repaint()


def _restart(label: QLabel) -> None:
    label.x = 0
    label.repaint()
    label.timer.start(20)

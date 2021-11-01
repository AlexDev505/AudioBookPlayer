from __future__ import annotations

import os
import pathlib
import ssl
import typing as ty
import urllib.request
import shutil

from PyQt5.QtCore import (
    QBasicTimer,
    QEasingCurve,
    QEvent,
    QObject,
    QPropertyAnimation,
    QSize,
    QTimer,
    Qt,
    pyqtSignal,
)
from PyQt5.QtGui import QMovie, QPixmap, QIcon
from PyQt5.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QToolTip,
    QVBoxLayout,
    QFileDialog,
)

from database.tables.books import Books, Status
from drivers import drivers, BaseDownloadProcessHandler
from tools import convert_into_bits, Cache, BaseWorker
from .add_book_page import SearchWorker
import styles
from database import Config

if ty.TYPE_CHECKING:
    from PyQt5 import QtCore
    from main_window import MainWindow
    from database.tables.books import Book


def setDirWithBooks(main_window: MainWindow) -> None:
    path = QFileDialog.getExistingDirectory(main_window, "Выберите папку")
    if path is None or not str(path).strip():
        return

    main_window.openLoadingPage()

    file_paths = []
    roots = []
    for root, _, file_names in os.walk(os.environ["books_folder"]):
        for file_name in file_names:
            file_paths.append(
                os.path.join(root.split(os.environ["books_folder"])[1], file_name)[1:]
            )
        roots.append(root)

    for file_path in file_paths:
        new_file_path = pathlib.Path(path, file_path)
        if not new_file_path.exists():
            new_file_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(
            os.path.join(os.environ["books_folder"], file_path),
            os.path.join(path, file_path),
        )
        try:
            os.remove(os.path.join(os.environ["books_folder"], file_path))
        except Exception:
            pass

    for root in roots[::-1]:
        try:
            os.rmdir(root)
        except Exception:
            pass

    Config.update(books_folder=path)

    main_window.stackedWidget.setCurrentWidget(main_window.settingsPage)
    QMessageBox.information(main_window, "Информация", "Папка успешно изменена")


def changeTheme(main_window: MainWindow) -> None:
    main_window.centralwidget.setStyleSheet(
        styles.get_style_sheet(main_window.themeSelecror.currentText())
        or styles.DEFAULT_STYLESHEET
    )

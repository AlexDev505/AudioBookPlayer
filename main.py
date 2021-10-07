from __future__ import annotations

import sys
import typing as ty
from inspect import isclass

from PyQt5.QtWidgets import QApplication

import config  # Noqa
from drivers.exceptions import DriverError
from main_window import MainWindow
from start_app import StartAppWindow


def startApp():
    window = StartAppWindow()
    window.finished.connect(lambda err: finishLoading(window, err))
    return window


def finishLoading(window: StartAppWindow, err: ty.Union[ty.Any, ty.Type[DriverError]]):
    window.close()
    main_window = MainWindow()
    main_window.show()

    if isclass(err) and issubclass(err, DriverError):
        err = err(main_window)
        main_window.openInfoPage(**err.to_dict())
        main_window.menuBtn.click()
        main_window.menuFrame.setDisabled(True)
        main_window.controlPanel.hide()


def startMainWindow():
    window = MainWindow()
    window.installEventFilter(window)
    return window


def main():
    app = QApplication([])
    window = startApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

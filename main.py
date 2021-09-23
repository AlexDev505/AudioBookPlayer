from __future__ import annotations

import sys
import time
import typing as ty

from PyQt5 import QtWidgets

from resources import icons_rc  # noqa
from ui import UiMainWindow, SearchView, LibraryView, BookWidget


def view(func: ty.Callable[[Window], None]):
    def _wrapper(self: Window):
        self.prepare_to_change_view()
        return func(self)

    return _wrapper


class Window(QtWidgets.QMainWindow):
    def __init__(self):
        super(Window, self).__init__()
        self.ui = UiMainWindow()
        self.ui.setupUi(self)

        self.setup_signals()

        self._is_open_menu = True

        self.library: LibraryView = None  # noqa

    def setup_signals(self) -> None:
        """
        Подключаем обработчики сигналов.
        """
        self.ui.menu_btn.clicked.connect(self.toggle_menu)

        self.ui.my_books_btn.clicked.connect(self.open_books_view)
        self.ui.search_btn.clicked.connect(self.open_search_view)

    @view
    def open_search_view(self) -> None:
        """
        Открывает страницу "Поиск".
        """
        self.ui.my_books_btn.setChecked(False)
        self.ui.my_favorite_btn.setChecked(False)
        self.ui.search_btn.setChecked(True)
        self.ui.settings_btn.setChecked(False)
        SearchView(self.ui.frame)

    @view
    def open_books_view(self) -> None:
        """
        Открывает страницу "Мои книги".
        """
        self.ui.my_books_btn.setChecked(True)
        self.ui.my_favorite_btn.setChecked(False)
        self.ui.search_btn.setChecked(False)
        self.ui.settings_btn.setChecked(False)

        self.library = LibraryView(self.ui.frame)

        # Я не знаю почему, но без этого с полосе прокрутки не применяются стили...
        self.library.scrollArea.setStyleSheet(self.library.scrollArea.styleSheet())

        for _ in range(2):
            frame = QtWidgets.QFrame()
            l = QtWidgets.QHBoxLayout(frame)
            b1 = BookWidget(frame)
            b2 = BookWidget(frame)
            l.addWidget(b1)
            l.addWidget(b2)
            self.library.scrollAreaWidgetContents.layout().addWidget(frame)

    def prepare_to_change_view(self):
        """
        Подготавливает приложение к переходу в другой пункт меню.
        :return:
        """
        self.library = None
        self.clear_frame()

    def clear_frame(self) -> None:
        """
        Очищает `self.ui.frame` для дальнейшего заполнения новыми элементами.
        """
        if len(self.ui.frame.children()) > 0:
            for i in range(len(self.ui.frame.children())):
                if not isinstance(
                    (obj := self.ui.frame.children()[i]),
                    QtWidgets.QVBoxLayout,
                ):  # Не удаляем макет
                    obj.deleteLater()

    def toggle_menu(self) -> None:
        """
        Открывает/закрывает меню.
        """
        if self._is_open_menu:
            self.ui.menu_btn.setChecked(True)
            self._close_menu()
        else:
            self.ui.menu_btn.setChecked(False)
            self._open_menu()
        self._is_open_menu = not self._is_open_menu

    def _open_menu(self) -> None:
        self._animate_menu_moving(70, 250)

    def _close_menu(self) -> None:
        self._animate_menu_moving(250, 70)

    def _animate_menu_moving(self, x1: int, x2: int) -> None:
        w = (x1 - x2) // 9
        widths = [x1 - w * i for i in range(1, 9 + 1)]
        for width in widths:
            self.ui.menu_frame.setMaximumSize(width, 16777215)
            self.ui.menu_frame.setMinimumSize(width, 0)
            app.processEvents()
            time.sleep(0.001)


app = QtWidgets.QApplication([])
application = Window()
application.show()

sys.exit(app.exec())

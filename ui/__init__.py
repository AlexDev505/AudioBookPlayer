from PyQt5 import QtWidgets

from .main import UiMainWindow
from .search_view import UiSearchView
from .library_view import UiLibraryView
from .book import UiBook


class View(QtWidgets.QFrame):
    def __init__(self, container: QtWidgets.QFrame):
        super(View, self).__init__(container)
        container.layout().addWidget(self)
        self.setupUi(self)
        self.show()


class SearchView(View, UiSearchView):
    pass


class LibraryView(View, UiLibraryView):
    pass


class BookWidget(View, UiBook):
    pass


__all__ = [UiMainWindow, SearchView, LibraryView]

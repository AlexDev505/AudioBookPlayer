from . import books
from . import window_controls
from .js_api import JSApi


JSApi.sections.append(books.BooksApi)
JSApi.sections.append(window_controls.WindowControlsApi)

__all__ = ["JSApi"]

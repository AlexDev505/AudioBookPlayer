from . import books
from . import settings
from . import window_controls
from .js_api import JSApi


JSApi.sections.append(books.BooksApi)
JSApi.sections.append(window_controls.WindowControlsApi)
JSApi.sections.append(settings.SettingsApi)

__all__ = ["JSApi"]


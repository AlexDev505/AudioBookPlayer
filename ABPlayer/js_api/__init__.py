from . import books, settings, window_controls, smtc
from .js_api import JSApi

JSApi.sections.append(books.BooksApi)
JSApi.sections.append(window_controls.WindowControlsApi)
JSApi.sections.append(settings.SettingsApi)
JSApi.sections.append(smtc.MediaApi)

__all__ = ["JSApi"]

import os
import sys


# CONFIG SETUP
# Путь к директории приложения
os.environ["APP_DIR"] = os.path.join(os.environ["LOCALAPPDATA"], "AudioBookPlayer")
if not os.path.exists(os.environ["APP_DIR"]):
    os.mkdir(os.environ["APP_DIR"])
# Путь к файлу конфигурации
os.environ["CONFIG_PATH"] = os.path.join(os.environ["APP_DIR"], "config.json")
# Путь к файлу базы данных библиотеки
os.environ["DATABASE_PATH"] = os.path.join(os.environ["APP_DIR"], "library.sqlite")
# Путь к файлу отладки
os.environ["DEBUG_PATH"] = os.path.join(os.environ["APP_DIR"], "debug.log")
# Путь к файлу с временными данными
os.environ["TEMP_PATH"] = os.path.join(os.environ["APP_DIR"], "temp.txt")
# Версия приложения
os.environ["VERSION"] = "0.0.0"

# TODO: remove
os.environ["CONSOLE"] = "1"
os.environ["DEBUG"] = "1"


from logger import logger  # noqa


def main() -> None:
    import webview
    from js_api import JSApi
    from web.app import app

    import config
    from database import Database

    config.init()
    with Database() as db:
        db.create_library()

    def _on_loaded():
        logger.info(f"Loading {window.get_current_url()}")

    def _on_closed():
        logger.info("Application closed\n\n")

    def _on_shown():
        logger.info("Application started")

    logger.info("Launching...")

    js_api = JSApi()
    window = webview.create_window(
        "ABPLayer",
        app,
        width=1000,
        height=650,
        frameless=True,
        easy_drag=False,
        min_size=(820, 520),
        background_color="#000",
        js_api=js_api,
    )

    # Добавляем обработчики событий
    window.events.loaded += _on_loaded
    window.events.closed += _on_closed
    window.events.shown += _on_shown

    webview.start(js_api.init, debug=bool(os.environ["DEBUG"]))


if __name__ == "__main__":
    main()

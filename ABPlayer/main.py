import os

from tools import pretty_view


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
os.environ["LOGGING_LEVEL"] = "TRACE"


from logger import logger  # noqa


def main() -> None:
    import webview
    from starting_window import create_starting_window

    logger.opt(colors=True).debug(
        "starting params: "
        + pretty_view(
            dict(
                app_dir=os.environ["APP_DIR"],
                debug=bool(os.getenv("DEBUG")),
                logging_level=os.environ["LOGGING_LEVEL"],
            ),
        ),
    )

    create_starting_window()
    webview.start(debug=bool(os.environ["DEBUG"]))


if __name__ == "__main__":
    main()

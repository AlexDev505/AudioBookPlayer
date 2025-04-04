import os
import platform


# CONFIG SETUP
# Путь к директории приложения
os.environ["APP_DIR"] = os.path.join(os.environ["LOCALAPPDATA"], "AudioBookPlayer")
if not os.path.exists(os.environ["APP_DIR"]):
    os.mkdir(os.environ["APP_DIR"])
# Путь к файлу отладки
os.environ["DEBUG_PATH"] = os.path.join(os.environ["APP_DIR"], "debug.log")
# Архитектура системы
os.environ["ARCH"] = " x32" if platform.architecture()[0] == "32bit" else ""
os.environ["UPDATER_VERSION"] = "1.0.0"

# DEV
os.environ["CONSOLE"] = "1"
os.environ["DEBUG"] = "1"
os.environ["LOGGING_LEVEL"] = "TRACE"


from logger import logger  # noqa


def main(version: str, only_stable: bool) -> None:
    os.environ["VERSION"] = version
    if only_stable:
        os.environ["ONLY_STABLE"] = "1"

    import webview
    from updating_window import create_updating_window

    create_updating_window()
    webview.start(
        debug=bool(os.environ.get("DEBUG")),
        storage_path=os.path.join(os.environ["APP_DIR"], "WebViewCache"),
    )


if __name__ == "__main__":
    main("2.2.1", False)

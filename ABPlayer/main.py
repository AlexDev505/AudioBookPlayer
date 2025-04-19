import os
import platform

from tools import pretty_view


# CONFIG SETUP
# Path to the application directory
os.environ["APP_DIR"] = os.path.join(os.environ["LOCALAPPDATA"], "AudioBookPlayer")
if not os.path.exists(os.environ["APP_DIR"]):
    os.mkdir(os.environ["APP_DIR"])
# Path to the configuration file
os.environ["CONFIG_PATH"] = os.path.join(os.environ["APP_DIR"], "config.json")
# Path to the library database file
os.environ["DATABASE_PATH"] = os.path.join(os.environ["APP_DIR"], "library.sqlite")
# Path to the debug file
os.environ["DEBUG_PATH"] = os.path.join(os.environ["APP_DIR"], "debug.log")
# Path to the temporary data file
os.environ["TEMP_PATH"] = os.path.join(os.environ["APP_DIR"], "temp.txt")
# Path to the dir with licensed drivers auth
os.environ["AUTH_DIR"] = os.path.join(os.environ["APP_DIR"], "auth")
# System architecture
os.environ["ARCH"] = " x32" if platform.architecture()[0] == "32bit" else ""
# App version
os.environ["VERSION"] = "3.0.0-alpha.1"

# DEV
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
                debug=bool(os.environ.get("DEBUG")),
                logging_level=os.environ["LOGGING_LEVEL"],
            ),
        ),
    )

    create_starting_window()
    webview.start(
        debug=bool(os.environ.get("DEBUG")),
        storage_path=os.path.join(os.environ["APP_DIR"], "WebViewCache"),
    )


if __name__ == "__main__":
    main()

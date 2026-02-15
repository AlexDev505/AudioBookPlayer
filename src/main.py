import os
import platform

import platformdirs

from tools import pretty_view

# CONFIG SETUP
# Path to the application directory
os.environ["APP_DIR"] = os.path.join(
    platformdirs.user_data_dir(), "AudioBookPlayer-DEV"
)

if not os.path.exists(os.environ["APP_DIR"]):
    os.mkdir(os.environ["APP_DIR"])
# Path to the configuration file
os.environ["CONFIG_PATH"] = os.path.join(os.environ["APP_DIR"], "config.json")
# Path to the library database file
os.environ["DATABASE_PATH"] = os.path.join(
    os.environ["APP_DIR"], "library.sqlite"
)
# Path to the debug file
os.environ["DEBUG_PATH"] = os.path.join(os.environ["APP_DIR"], "debug.log")
# Path to the temporary data file
os.environ["TEMP_PATH"] = os.path.join(os.environ["APP_DIR"], "temp.txt")
# Path to the dir with licensed drivers auth
os.environ["AUTH_DIR"] = os.path.join(os.environ["APP_DIR"], "auth")
# Platform params
os.environ["PLATFORM"] = platform.system()
os.environ["ARCH"] = platform.architecture()[0]
# App version
os.environ["VERSION"] = "4.0.0-dev.0"

# DEV
os.environ["DEBUG"] = "1"
os.environ["CONSOLE"] = "1"
os.environ["LOGGING_LEVEL"] = "DEBUG"

from logger import logger  # noqa


def main() -> None:
    import webview

    from starting_window import create_starting_window

    logger.opt(colors=True).debug(
        "starting params: "
        + pretty_view(
            dict(
                platform=os.environ["PLATFORM"],
                arch=os.environ["ARCH"],
                app_dir=os.environ["APP_DIR"],
                debug=bool(os.environ.get("DEBUG")),
                logging_level=os.environ["LOGGING_LEVEL"],
            ),
        ),
    )

    create_starting_window()
    webview.start(
        ssl=True,
        debug=bool(os.environ.get("DEBUG")),
        storage_path=os.path.join(os.environ["APP_DIR"], "WebViewCache"),
    )


if __name__ == "__main__":
    main()

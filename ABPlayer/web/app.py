import os
import re
import sys

from flask import Flask, render_template, send_from_directory

import temp_file


if getattr(sys, "frozen", False):
    ROOT_DIR = getattr(sys, "_MEIPASS")
else:
    ROOT_DIR = os.path.dirname(__file__)

app = Flask(
    __name__,
    template_folder=os.path.join(ROOT_DIR, "templates"),
    static_folder=os.path.join(ROOT_DIR, "static"),
)
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 1  # disable caching


@app.route("/")
def index():
    temp_data = temp_file.load()
    return render_template(
        "base.html",
        app_version=os.environ["VERSION"],
        dark_theme=bool(int(os.environ["dark_theme"])),
        lang=os.environ["language"],
        is_main_menu_opened=temp_data.get("is_main_menu_opened", True),
        is_filter_menu_opened=temp_data.get("is_filter_menu_opened", True),
        volume=temp_data.get("volume", 50),
        speed=temp_data.get("speed", 1),
        last_listened_book_bid=temp_data.get("last_listened_book_bid", None),
        only_stable=temp_data.get("only_stable", False),
        stable_version=(
            re.fullmatch(r"\d+\.\d+\.\d+", os.environ["VERSION"]) is not None
        ),
        required_drivers=(
            required_drivers.split(",")
            if (required_drivers := temp_data.get("required_drivers", ""))
            else None
        ),
        gettext=_,
    )


@app.route("/starting_window")
def start_app():
    return render_template("starting_window.html")


@app.route("/library/<path:file_path>")
def library_cdn(file_path: str):
    return send_from_directory(os.environ["books_folder"], file_path)


if __name__ == "__main__":
    app.run(debug=True)

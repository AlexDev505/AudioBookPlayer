import os
import sys
import zipfile
from io import BytesIO
from urllib.parse import unquote

import requests
from flask import Flask, render_template, send_file, send_from_directory

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
        platform=os.environ["PLATFORM"],
        app_version=os.environ["VERSION"],
        dark_theme=bool(int(os.environ["dark_theme"])),
        lang=os.environ["language"],
        is_main_menu_opened=temp_data.get("is_main_menu_opened", True),
        volume=temp_data.get("volume", 50),
        speed=temp_data.get("speed", 1),
        gettext=_,
    )


@app.route("/starting_window")
def start_app():
    return render_template("starting_window.html")


@app.route("/library/<path:file_path>")
def library_cdn(file_path: str):
    return send_from_directory(
        os.environ["books_folder"],
        file_path := unquote(file_path).replace("\\", "/"),
        download_name=file_path.split("/")[-1],
    )


@app.route("/text_book_content/<string:url>")
def text_book_content_cdn(url: str):
    resp = requests.get(unquote(url))
    buffer = BytesIO(resp.content)
    buffer.seek(0)

    with zipfile.ZipFile(buffer) as zip_file:
        file_name = zip_file.namelist()[0]
        content = zip_file.read(file_name)

    return send_file(
        BytesIO(content), as_attachment=True, download_name=file_name
    )


if __name__ == "__main__":
    app.run(debug=True)

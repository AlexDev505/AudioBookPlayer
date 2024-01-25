import os
import sys

from flask import Flask, render_template

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
        is_main_menu_opened=temp_data.get("is_main_menu_opened", True),
        is_filter_menu_opened=temp_data.get("is_filter_menu_opened", True),
        required_drivers=(
            required_drivers.split(",")
            if (required_drivers := temp_data.get("required_drivers", ""))
            else None
        ),
    )


if __name__ == "__main__":
    app.run(debug=True)

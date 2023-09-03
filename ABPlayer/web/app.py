import os
import sys

from flask import Flask, render_template


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
    return render_template(
        "home.html",
    )


if __name__ == "__main__":
    app.run(debug=True)

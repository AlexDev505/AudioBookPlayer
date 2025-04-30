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


@app.route("/")
def start_app():
    return render_template("main.html")


if __name__ == "__main__":
    app.run(debug=True)

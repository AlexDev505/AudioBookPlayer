import os
import json
from dataclasses import asdict

import orjson


os.environ["APP_DIR"] = os.path.join(os.environ["LOCALAPPDATA"], "AudioBookPlayer")
os.environ["DATABASE_PATH"] = os.path.join(os.environ["APP_DIR"], "library.sqlite")

from database import Database  # noqa

with Database() as db:
    library = db.get_libray(1, 0, None, "", "", False, None)
    book = library[0]
    print(json.dumps(book.to_dump()))

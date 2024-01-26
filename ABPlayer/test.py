import os

os.environ["APP_DIR"] = os.path.join(os.environ["LOCALAPPDATA"], "AudioBookPlayer")
os.environ["DATABASE_PATH"] = os.path.join(os.environ["APP_DIR"], "library.sqlite")
os.environ["books_folder"] = r"E:\books"

from database import Database


with Database() as db:
    for book in db.get_libray(100, 0, None, None, None, None, None, None, None):
        # if os.path.exists(book.dir_path):
        if book.files:
            book.save_to_storage()

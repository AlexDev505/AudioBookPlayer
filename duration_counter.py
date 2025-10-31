"""

Script for counting duration of library.
Shows top 3 largest books and series.

"""

import json
import math
import os
import subprocess
import sys
import threading
import time

FILE_FORMATS = [".mp3", ".m4a", ".wav"]


def get_audio_file_duration(file_path: str) -> float:
    """
    :param file_path: The path to the Audio File.
    :returns: The duration of the audio file in seconds.
    """
    result = subprocess.check_output(
        rf'ffprobe -v quiet -show_streams -of json "{file_path}"',
        shell=True,
    ).decode()
    fields = json.loads(result)["streams"][0]
    return float(fields["duration"])


def convert_from_bytes(bytes_value: int) -> str:
    """
    :param bytes_value: The number of bytes.
    :returns: String in format <number> <unit>
    """
    if bytes_value == 0:
        return "0B"
    size_name = ("б", "КБ", "МБ", "ГБ", "ТБ", "ПБ", "EB", "ZB", "YB")
    i = int(math.floor(math.log(bytes_value, 1024)))
    p = math.pow(1024, i)
    s = round(bytes_value / p, 2)
    return "%s %s" % (s, size_name[i])


books: dict[str, list[str | int] | int] = {}
count_books = count_files = 0
for r, _, files in os.walk("."):
    for file in files:
        if any(file.endswith(ext) for ext in FILE_FORMATS):
            count_files += 1
            if r not in books:
                count_books += 1
                books[r] = []
            books[r].append(f"{r}/{file}")

print(f"всего книг: {count_books}\nфайлов: {count_files}")
unhandled = []
for k, vs in books.items():
    for v in vs:
        unhandled.append((k, v))
    books[k] = [len(vs), 0]
duration = size = completed_files = completed_books = 0


def worker():
    global size, duration, completed_files, completed_books
    while unhandled:
        book_root, book_file = unhandled.pop(0)
        sys.stdout.write(
            f"\r{completed_books}/{count_books} {completed_files}/{count_files}"
        )
        sys.stdout.flush()
        size += os.path.getsize(book_file)
        d = get_audio_file_duration(book_file)
        completed_files += 1
        duration += d
        books[book_root][1] += d
        books[book_root][0] -= 1
        if books[book_root][0] == 0:
            completed_books += 1
            books[book_root] = books[book_root][1]


threads = []
for _ in range(15):
    t = threading.Thread(target=worker)
    t.start()
    threads.append(t)

while any(t.is_alive() for t in threads):
    time.sleep(0.1)
books: dict[str, int]

sys.stdout.write("\r" + " " * 50)
sys.stdout.flush()
print()


def hms(sec: int):
    return dict(h=sec // 3600, m=sec // 60 % 60, s=sec % 60)


h, m, s = hms(duration).values()
print(f"{h} часов {m} минут")
if h > 24:
    print(round(h / 24, 1), " суток")
if h > 24 * 7:
    print(round(h / (24 * 7), 1), " недель")
if h > 24 * 30:
    print(round(h / (24 * 30), 1), " месяцев")
print(f"Общий размер: {convert_from_bytes(size)}")

if len(books) >= 3:
    print("\n   Самые продолжительные книги\n")
    longest = list(sorted(books, key=lambda x: books[x], reverse=True))
    for i in range(3):
        print(
            longest[i],
            "{h} часов {m} минут\n".format(**hms(books[longest[i]])),
            sep="\n",
        )

series = {}
for r, v in books.items():
    sr = r[: r.rfind("\\")]
    if sr not in series:
        series[sr] = 0
    series[sr] += v

if len(series) >= 3:
    print("\n   Самые продолжительные серии\n")
    longest = list(sorted(series, key=lambda x: series[x], reverse=True))
    for i in range(3):
        print(
            longest[i],
            "{h} часов {m} минут\n".format(**hms(series[longest[i]])),
            sep="\n",
        )

input()

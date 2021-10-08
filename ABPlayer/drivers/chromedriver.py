"""

Утилита, скачивающая подходящую версию драйвера Chrome.
Создано на основе https://pypi.org/project/chromedriver-autoinstaller/

"""

from __future__ import annotations

import os
import re
import subprocess
import typing as ty
import urllib.error
import urllib.request
import xml.etree.ElementTree as elemTree
import zipfile
from io import BytesIO

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import pyqtSignal


def check_version(driver_path: str, required_version: str) -> bool:
    """
    Проверяет соответствие версий установленного браузера и драйвера.
    :param driver_path: Путь к драйверу.
    :param required_version: Версия браузера.
    :return:
    """
    try:
        version = subprocess.check_output([driver_path, "-v"])
        version = re.match(r".*?([\d.]+).*?", version.decode("utf-8"))[1]
        if version == required_version:
            return True
    except Exception:
        return False
    return False


def get_chrome_version() -> str:
    """
    :return: Версия установленного браузера Chrome.
    :raise: IndexError.
    """
    process = subprocess.Popen(
        [
            "reg",
            "query",
            "HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon",
            "/v",
            "version",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    version = process.communicate()[0].decode("UTF-8").strip().split()[-1]
    return version


def get_matched_chromedriver_version(version: str) -> str:
    """
    :param version: Версия браузера Chrome.
    :return: Версия chromedriver.
    """
    doc = urllib.request.urlopen("https://chromedriver.storage.googleapis.com").read()
    root = elemTree.fromstring(doc)
    for k in root.iter("{http://doc.s3.amazonaws.com/2006-03-01}Key"):
        if k.text.find(version.split(".")[0] + ".") == 0:
            return k.text.split("/")[0]


def download_chromedriver(signal: pyqtSignal(bool, str) = None) -> str:
    """
    Скачивает, распаковывает и устанавливает chromedriver.
    Если двоичный файл chromedriver найден в PATH, он будет скопирован,
    в противном случае он будет загружен.
    :param signal: Инстанс сигнала, для обратной связи.
    :return: Путь к chromedriver.
    :raises: "Not available version", "download error"
    """
    chrome_version = get_chrome_version()
    chromedriver_version = get_matched_chromedriver_version(chrome_version)
    if not chromedriver_version:
        raise FileNotFoundError("Not available version")
    # Директория, где хранится драйвер
    chromedriver_dir = os.path.abspath(os.path.dirname(__file__))
    # Путь к драйверу
    chromedriver_filepath = os.path.join(chromedriver_dir, "chromedriver.exe")
    if not os.path.isfile(chromedriver_filepath) or not check_version(
        chromedriver_filepath, chromedriver_version
    ):
        if signal:
            signal.emit("Скачивание драйвера", None)
        if not os.path.isdir(chromedriver_dir):
            # Создаём директорию, в которой будет храниться драйвер
            os.mkdir(chromedriver_dir)
        url = (
            f"https://chromedriver.storage.googleapis.com/"
            f"{chromedriver_version}/chromedriver_win32.zip"
        )  # Ссылка на архив с нужным драйвером
        response = urllib.request.urlopen(url)  # Скачивание
        if response.getcode() != 200:
            raise urllib.error.URLError("download error")
        archive = BytesIO(response.read())
        with zipfile.ZipFile(archive) as zip_file:  # Разархивация
            zip_file.extract("chromedriver.exe", chromedriver_dir)
    if not os.access(chromedriver_filepath, os.X_OK):
        os.chmod(chromedriver_filepath, 0o744)
    return chromedriver_filepath


def install(signal: pyqtSignal(bool, str) = None) -> None:
    """
    Добавляет каталог двоичного файла chromedriver к PATH.
    :param signal: Инстанс сигнала, для обратной связи.
    """
    chromedriver_filepath = download_chromedriver(signal)
    if not chromedriver_filepath:
        raise SystemError("Downloading fail")
    if signal:
        signal.emit("Установка драйвера", None)
    chromedriver_dir = os.path.dirname(chromedriver_filepath)
    if "PATH" not in os.environ:
        os.environ["PATH"] = chromedriver_dir
    elif chromedriver_dir not in os.environ["PATH"]:
        os.environ["PATH"] = chromedriver_dir + ";" + os.environ["PATH"]

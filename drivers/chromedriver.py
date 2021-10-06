"""

Утилита, скачивающая подходящую версию драйвера Chrome.
Создано на основе https://pypi.org/project/chromedriver-autoinstaller/

"""

from __future__ import annotations

import os
import re
import subprocess
import urllib.error
import urllib.request
import xml.etree.ElementTree as elemTree
import zipfile
import typing as ty
from io import BytesIO

if ty.TYPE_CHECKING:
    from PyQt5.QtCore import pyqtSignal


def check_version(binary, required_version):
    try:
        version = subprocess.check_output([binary, "-v"])
        version = re.match(r".*?([\d.]+).*?", version.decode("utf-8"))[1]
        if version == required_version:
            return True
    except Exception:
        return False
    return False


def get_chrome_version():
    """
    :return: Версия установленного браузера Chrome.
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


def get_matched_chromedriver_version(version):
    """
    :param version: Версия браузера Chrome.
    :return: Версия chromedriver.
    """
    doc = urllib.request.urlopen("https://chromedriver.storage.googleapis.com").read()
    root = elemTree.fromstring(doc)
    for k in root.iter("{http://doc.s3.amazonaws.com/2006-03-01}Key"):
        if k.text.find(version.split(".")[0] + ".") == 0:
            return k.text.split("/")[0]


def download_chromedriver(signal: pyqtSignal(bool, str) = None):
    """
    Downloads, unzips and installs chromedriver.
    If a chromedriver binary is found in PATH it will be copied, otherwise downloaded.
    :param signal: Инстанс сигнала, для обратной связи.
    :return: Путь к chromedriver.
    """
    chrome_version = get_chrome_version()
    chromedriver_version = get_matched_chromedriver_version(chrome_version)
    if not chromedriver_version:
        raise FileNotFoundError("Не найден драйвер для вашей версии Chrome")
    chromedriver_dir = os.path.abspath(os.path.dirname(__file__))
    chromedriver_filepath = os.path.join(chromedriver_dir, "chromedriver.exe")
    if not os.path.isfile(chromedriver_filepath) or not check_version(
        chromedriver_filepath, chromedriver_version
    ):
        if signal:
            signal.emit(True, "Скачивание драйвера")
        if not os.path.isdir(chromedriver_dir):
            os.mkdir(chromedriver_dir)
        url = (
            f"https://chromedriver.storage.googleapis.com/"
            f"{chromedriver_version}/chromedriver_win32.zip"
        )
        try:
            response = urllib.request.urlopen(url)
            if response.getcode() != 200:
                raise urllib.error.URLError("Not Found")
        except urllib.error.URLError:
            raise RuntimeError(f"Ошибка при скачивании драйвера {url}")
        archive = BytesIO(response.read())
        with zipfile.ZipFile(archive) as zip_file:
            zip_file.extract("chromedriver.exe", chromedriver_dir)
    if not os.access(chromedriver_filepath, os.X_OK):
        os.chmod(chromedriver_filepath, 0o744)
    return chromedriver_filepath


def install(signal: pyqtSignal(bool, str) = None):
    """
    Добавляет каталог двоичного файла chromedriver к PATH.
    :param signal: Инстанс сигнала, для обратной связи.
    """
    chromedriver_filepath = download_chromedriver(signal)
    if not chromedriver_filepath:
        raise SystemError("Невозможно скачать драйвер")
    signal.emit(True, "Установка драйвера")
    chromedriver_dir = os.path.dirname(chromedriver_filepath)
    if "PATH" not in os.environ:
        os.environ["PATH"] = chromedriver_dir
    elif chromedriver_dir not in os.environ["PATH"]:
        os.environ["PATH"] = chromedriver_dir + ";" + os.environ["PATH"]

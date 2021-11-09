"""

Утилита, скачивающая подходящую версию драйвера Chrome.
Создано на основе https://pypi.org/project/chromedriver-autoinstaller/

Модификация стандартного `selenium.webdriver.Chrome`.
Скрывает консоль chromedriver.exe
Основано на:
https://selenium-python.readthedocs.io/api.html?highlight=service#selenium.webdriver.common.service.Service
и
https://selenium-python.readthedocs.io/api.html?highlight=chrome%20webdriver#module-selenium.webdriver.chrome.webdriver

"""

from __future__ import annotations

import errno
import os
import platform
import re
import subprocess
import time
import typing as ty
import urllib.error
import urllib.request
import warnings
import xml.etree.ElementTree as elemTree
import zipfile
from io import BytesIO

from loguru import logger
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome import service, webdriver, remote_connection
from selenium.webdriver.remote.webdriver import WebDriver as RemoteWebDriver

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
    logger.opt(colors=True).trace(f"Chrome: <y>{version}</y>")
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
    logger.trace("Checking for driver updates")
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
        logger.debug(f"Driver update to {chromedriver_version}")
        if signal:
            signal.emit("Скачивание драйвера", None)
        if not os.path.isdir(chromedriver_dir):
            # Создаём директорию, в которой будет храниться драйвер
            os.mkdir(chromedriver_dir)
        url = (
            f"https://chromedriver.storage.googleapis.com/"
            f"{chromedriver_version}/chromedriver_win32.zip"
        )  # Ссылка на архив с нужным драйвером
        logger.trace("Downloading the driver")
        response = urllib.request.urlopen(url)  # Скачивание
        if response.getcode() != 200:
            logger.error(f"download error. code: {response.getcode()}")
            raise urllib.error.URLError("download error")
        logger.trace("Unzipping the driver")
        archive = BytesIO(response.read())
        with zipfile.ZipFile(archive) as zip_file:  # Разархивация
            zip_file.extract("chromedriver.exe", chromedriver_dir)
        logger.opt(colors=True).debug(
            f"Driver updated to version <y>{chromedriver_version}</y>"
        )
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
        logger.error("Driver not installed")
        raise SystemError("Downloading fail")
    if signal:
        signal.emit("Установка драйвера", None)
    chromedriver_dir = os.path.dirname(chromedriver_filepath)
    if "PATH" not in os.environ:
        os.environ["PATH"] = chromedriver_dir
    elif chromedriver_dir not in os.environ["PATH"]:
        os.environ["PATH"] = chromedriver_dir + ";" + os.environ["PATH"]


class HiddenChromeService(service.Service):
    def start(self):
        try:
            cmd = [self.path]
            cmd.extend(self.command_line_args())

            if platform.system() == "Windows":
                info = subprocess.STARTUPINFO()
                info.dwFlags = subprocess.STARTF_USESHOWWINDOW
                info.wShowWindow = 0  # SW_HIDE (6 == SW_MINIMIZE)
            else:
                info = None

            self.process = subprocess.Popen(  # noqa
                cmd,
                env=self.env,
                close_fds=platform.system() != "Windows",
                startupinfo=info,
                stdout=self.log_file,
                stderr=self.log_file,
                stdin=subprocess.PIPE,
            )
        except TypeError:
            raise
        except OSError as err:
            if err.errno == errno.ENOENT:
                raise WebDriverException(
                    "'%s' executable needs to be in PATH. %s"
                    % (os.path.basename(self.path), self.start_error_message)
                )
            elif err.errno == errno.EACCES:
                raise WebDriverException(
                    "'%s' executable may have wrong permissions. %s"
                    % (os.path.basename(self.path), self.start_error_message)
                )
            else:
                raise
        except Exception as e:
            raise WebDriverException(
                "Executable %s must be in path. %s\n%s"
                % (os.path.basename(self.path), self.start_error_message, str(e))
            )
        count = 0
        while True:
            self.assert_process_still_running()
            if self.is_connectable():
                break
            count += 1
            time.sleep(1)
            if count == 30:
                raise WebDriverException(
                    "Can't connect to the Service %s" % (self.path,)
                )


class HiddenChromeWebDriver(webdriver.WebDriver):
    def __init__(
        self,
        executable_path="chromedriver",
        port=0,
        options=None,
        service_args=None,
        desired_capabilities=None,
        service_log_path=None,
        chrome_options=None,
        keep_alive=True,
    ):
        if chrome_options:
            warnings.warn(
                "use options instead of chrome_options",
                DeprecationWarning,
                stacklevel=2,
            )
            options = chrome_options

        if options is None:
            # desired_capabilities stays as passed in
            if desired_capabilities is None:
                desired_capabilities = self.create_options().to_capabilities()
        else:
            if desired_capabilities is None:
                desired_capabilities = options.to_capabilities()
            else:
                desired_capabilities.update(options.to_capabilities())

        self.service = HiddenChromeService(
            executable_path,
            port=port,
            service_args=service_args,
            log_path=service_log_path,
        )
        self.service.start()

        try:
            RemoteWebDriver.__init__(
                self,
                command_executor=remote_connection.ChromeRemoteConnection(
                    remote_server_addr=self.service.service_url, keep_alive=keep_alive
                ),
                desired_capabilities=desired_capabilities,
            )
        except Exception:
            self.quit()
            raise
        self._is_remote = False

"""

Builds updater to .exe

"""

import os
import platform
import re
import shutil

import PyInstaller.__main__

from version import Version


__version__ = Version(1, 1, 1)

arch = " x32" if platform.architecture()[0] == "32bit" else ""
dev_path = os.path.join(os.path.dirname(__file__), "..", "updater")
run_file_path = os.path.join(dev_path, "run.py")
main_file_path = os.path.join(dev_path, "main.py")


with open(main_file_path, encoding="utf-8") as file:
    text = file.read()
text = re.sub(
    r'os.environ\["UPDATER_VERSION"] = ".+"',
    f'os.environ["UPDATER_VERSION"] = "{__version__}"',
    text,
)
dev_env_vars = re.search(r"# DEV\s((.+\s)+\s)", text, re.MULTILINE)
if dev_env_vars:
    dev_env_vars = dev_env_vars.group(1).strip()
    text = text.replace(dev_env_vars, "")
with open(main_file_path, "w", encoding="utf-8") as file:
    file.write(text)

with open(r"sources/updater_version_file") as file:
    text = file.read()
text = re.sub(
    r"StringStruct\(u'(?P<name>(FileVersion)|(ProductVersion))', u'.+'\)",
    rf"StringStruct(u'\g<name>', u'{__version__}')",
    text,
)
with open(r"sources/updater_version_file", "w") as file:
    file.write(text)

# BUILD
PyInstaller.__main__.run(
    [
        run_file_path,
        "-D",
        f"-n=ABPlayerUpdater{arch}",
        f"--version-file=updater_version_file",
        "--icon=icon.ico",
        "--distpath=.",
        "--workpath=temp",
        "--specpath=sources",
        "-y",
        "-w",
        "--clean",
        "--onefile",
        f"--add-data={os.path.join(dev_path, 'web', 'static')};static",
        f"--add-data={os.path.join(dev_path, 'web', 'templates')};templates",
    ]
)
shutil.rmtree("temp")

if dev_env_vars:
    with open(main_file_path, encoding="utf-8") as file:
        text = file.read()
    text = text.replace("# DEV\n", f"# DEV\n{dev_env_vars}")
    with open(main_file_path, "w", encoding="utf-8") as file:
        file.write(text)

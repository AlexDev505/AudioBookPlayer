"""
    Сборка утилиты обновления в exe
"""

import os.path
import shutil

import PyInstaller.__main__

if not os.path.exists("updater/main.py"):
    if os.path.exists("sources/ABPUpdater.exe"):
        os.remove("sources/ABPUpdater.exe")
    if os.path.exists("sources/ABPUpdater.spec"):
        os.remove("sources/ABPUpdater.spec")
    exit()

PyInstaller.__main__.run(
    [
        "updater/main.py",
        "-D",
        "-n=ABPUpdater",
        "--icon=icon.ico",
        "--distpath=sources",
        "--workpath=sources/abpu_temp",
        "--specpath=sources",
        "-y",
        "--clean",
        "--onefile",
        "--noconsole",
    ]
)

shutil.rmtree("sources/abpu_temp")

"""

    Сборка приложения в exe.

    Сборка проекта осуществляется в 2 этапа.
    1. Сборка в exe. Осуществляется с помощью pyinstaller.
    2. Сборка в exe установщик, осуществляемая при помощи nsis.

"""
import os
import re
import shutil
import sys

import PyInstaller.__main__

os.system(f"{sys.executable} {os.path.abspath('./updater_setup.py')}")

__version__ = "1.0.0-beta.6"
target_dir = "ABPlayer"

# Изменяем версию в main.py
with open(r"..\ABPlayer\main.py", encoding="utf-8") as file:
    text = file.read()
text = re.sub(
    r'os.environ\["VERSION"] = ".+"', f'os.environ["VERSION"] = "{__version__}"', text
)
with open(r"..\ABPlayer\main.py", "w", encoding="utf-8") as file:
    file.write(text)

# Изменяем версию в установщике
with open("installer.nsi") as file:
    text = file.read()
text = re.sub(
    r'!define PRODUCT_VERSION ".+"', f'!define PRODUCT_VERSION "{__version__}"', text
)
# Добавляем вызов утилиты обновления
if os.path.exists(r"sources\ABPUpdater.exe"):
    if r'File "sources\ABPUpdater.exe"' not in text:
        text = re.sub(
            r'Section "AB Player" SEC01\n {2}SetOutPath "\$INSTDIR"',
            r'Section "AB Player" SEC01\n  SetOutPath "$INSTDIR"\n\n  '
            r'File "sources\\ABPUpdater.exe"\n  ExecWait "$INSTDIR\\ABPUpdater.exe"\n  '
            r'Delete "$INSTDIR\\ABPUpdater.exe"\n',
            text,
            flags=re.MULTILINE,
        )
else:
    if r'File "sources\ABPUpdater.exe"' in text:
        text = re.sub(
            r'\n\n {2}File "sources\\ABPUpdater.exe"\n'
            r' {2}ExecWait "\$INSTDIR\\ABPUpdater.exe"\n'
            r' {2}Delete "\$INSTDIR\\ABPUpdater.exe"\n',
            r"",
            text,
            flags=re.MULTILINE,
        )
with open("installer.nsi", "w") as file:
    file.write(text)

# Изменяем версию в version_file
with open(r"sources\version_file") as file:
    text = file.read()
text = re.sub(
    r"StringStruct\(u'(?P<name>(FileVersion)|(ProductVersion))', u'.+'\)",
    rf"StringStruct(u'\g<name>', u'{__version__}')",
    text,
)
with open(r"sources\version_file", "w") as file:
    file.write(text)

shutil.rmtree("ABPlayer", ignore_errors=True)

PyInstaller.__main__.run(
    [
        "../abplayer/run.py",
        "-D",
        "-n=ABPlayer",
        "--version-file=version_file",
        "--icon=icon.ico",
        "--distpath=.",
        "--workpath=abp_temp",
        "--specpath=sources",
        "-y",
        "--clean",
        "-w",
        "--hiddenimport=plyer.platforms.win.notification",
    ]
)

shutil.rmtree("abp_temp", ignore_errors=True)

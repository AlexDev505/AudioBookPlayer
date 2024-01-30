"""

    Сборка exe и формирование NSIS сценариев.

"""

import json
import os
import re
import shutil

import PyInstaller.__main__
import orjson

from prepare_nsis import prepare_installer, prepare_updater
from version import Version


__version__ = Version(2, 0, 0, "alpha", 1)
dev_path = os.path.join(os.path.dirname(__file__), "..", "ABPlayer")
run_file_path = os.path.join(dev_path, "run.py")
main_file_path = os.path.join(dev_path, "main.py")


# CHECK LAST BUILD

if os.path.exists("last_build.json"):
    with open("last_build.json", encoding="utf-8") as file:
        last_build = orjson.loads(file.read())

    last_build_version = Version.from_str(last_build["version"])
    if __version__ == last_build_version:
        if (
            input("the latest build was the same version. rebuild again? (y/n): ")
            != "y"
        ):
            exit()
    elif __version__ < last_build_version:
        print(
            "the last build was a larger version. you can't build the smaller version"
        )
        exit()
else:
    last_build = {}
    last_build_version = Version(0, 0, 0, "alpha", 0)

# CHANGE VERSIONS IN BUILD
with open(main_file_path, encoding="utf-8") as file:
    text = file.read()
text = re.sub(
    r'os.environ\["VERSION"] = ".+"',
    f'os.environ["VERSION"] = "{__version__}"',
    text,
)
with open(main_file_path, "w", encoding="utf-8") as file:
    file.write(text)

with open(r"sources/version_file") as file:
    text = file.read()
text = re.sub(
    r"StringStruct\(u'(?P<name>(FileVersion)|(ProductVersion))', u'.+'\)",
    rf"StringStruct(u'\g<name>', u'{__version__}')",
    text,
)
with open(r"sources/version_file", "w") as file:
    file.write(text)

# BUILD
shutil.rmtree("ABPlayer", ignore_errors=True)
PyInstaller.__main__.run(
    [
        run_file_path,
        "-D",
        "-n=ABPlayer",
        f"--version-file=version_file",
        "--icon=icon.ico",
        "--distpath=.",
        "--workpath=temp",
        "--specpath=sources",
        "-y",
        "--clean",
        # "-w",
        # "--onefile",
        f"--add-data={os.path.join(dev_path, 'web', 'static')};static",
        f"--add-data={os.path.join(dev_path, 'web', 'templates')};templates",
    ]
)
shutil.rmtree("temp")

# SAVING INFO ABOUT CURRENT BUILD
print("\nSaving build info")
current_build = {"version": str(__version__), "files": {}}
for root, _, file_names in os.walk("ABPlayer"):
    current_build["files"][root] = file_names
with open("last_build.json", "w", encoding="utf-8") as file:
    file.write(json.dumps(current_build, indent=4))

print("Preparing installer")
prepare_installer(current_build)
if last_build and __version__ > last_build_version:
    update_uninstaller = input("update_uninstaller? (y/n): ") == "y"
    print("Preparing updater")
    prepare_updater(last_build, current_build, update_uninstaller)

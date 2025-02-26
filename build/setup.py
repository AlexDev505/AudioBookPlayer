"""

    Building exe and generating NSIS scripts.

"""

import json
import os
import re
import shutil

import PyInstaller.__main__
import orjson

from prepare_nsis import prepare_nsis
from version import Version


DEV: bool = False
__version__ = Version(2, 1, 3)
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
dev_env_vars = re.search(r"# DEV\s((.+\s)+\s)", text, re.MULTILINE)
if not DEV and dev_env_vars:
    dev_env_vars = dev_env_vars.group(1).strip()
    text = text.replace(dev_env_vars, "")
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
        "-w" if not DEV else "",
        # "--onefile",
        f"--add-data={os.path.join(dev_path, 'web', 'static')};static",
        f"--add-data={os.path.join(dev_path, 'web', 'templates')};templates",
        f"--add-data={os.path.join(dev_path, 'drivers', 'bin')};bin",
    ]
)
shutil.rmtree("temp")

if not DEV and dev_env_vars:
    with open(main_file_path, encoding="utf-8") as file:
        text = file.read()
    text = text.replace("# DEV\n", f"# DEV\n{dev_env_vars}")
    with open(main_file_path, "w", encoding="utf-8") as file:
        file.write(text)

# SAVING INFO ABOUT CURRENT BUILD
print("\nSaving build info")
current_build = {"version": str(__version__), "files": {}}
for root, _, file_names in os.walk("ABPlayer"):
    current_build["files"][root] = file_names
with open("last_build.json", "w", encoding="utf-8") as file:
    file.write(json.dumps(current_build, indent=4))

print("Preparing nsis")
prepare_nsis(current_build)

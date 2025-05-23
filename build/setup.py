"""

Assembly EXE, Formation of NSIS Scenario, prepare update.

All non -DEV builds are stored in the `updates` directory as new updates.
Creates `updates/<version>/<arch>/update.json` that stored:
hashes of all files, a list of changed and deleted files from the last stable release.
Inserts new versions at start of `updates/updates.json`
 (updates.keys()[0] - latest release).
In `updates/updates.json` u can mark version as `manual`
 and specify new versions of updater.
If release marked as `manual` - ABPlayerSetup.exe will be used, while updating.


Startup args:
    version: str
    --dev if given build will be DEV.
    --manual if given update will be marked as `manual`.
    --mark-as-latest if given this version will be saved in `last_build` file.
    --updater=<str> specify version of updater for this release.

"""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
from pathlib import Path

import PyInstaller.__main__
import orjson

from prepare_nsis import prepare_nsis
from version import Version


parser = argparse.ArgumentParser()
parser.add_argument("version", type=str)
parser.add_argument("--dev", action="store_true", default=False)
parser.add_argument("--manual", action="store_true", default=False)
parser.add_argument("--mark-as-latest", action="store_true", default=False)
parser.add_argument("--updater", type=str, default="")
args = parser.parse_args()

DEV: bool = args.dev
__version__ = Version.from_str(args.version)
locales = ["en", "ru"]
arch = " x32" if platform.architecture()[0] == "32bit" else ""
dev_path = os.path.join(os.path.dirname(__file__), "..", "ABPlayer")
run_file_path = os.path.join(dev_path, "run.py")
main_file_path = os.path.join(dev_path, "main.py")
updates_file_path = os.path.join("updates", "updates.json")
update_dir_path = os.path.join(
    "updates",
    str(__version__),
    "x32" if platform.architecture()[0] == "32bit" else "x64",
)
update_file_path = os.path.join(update_dir_path, "update.json")
last_build_file_path = os.path.join("last_build")

save_update = not DEV
if not DEV and os.path.exists(update_dir_path):
    save_update = (
        input("update with this version already exists, rewrite it? [y/N]: ") == "y"
    )

# CHANGE VERSIONS IN BUILD
with open(main_file_path, encoding="utf-8") as file:
    text = file.read()
text = re.sub(
    r'os.environ\["VERSION"] = ".+"',
    f'os.environ["VERSION"] = "{__version__}"',
    text,
)
dev_env_vars = re.search(r"# DEV\s((.+\s)+\s)", text, re.MULTILINE)
# remove dev environ variables in not dev build
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
shutil.rmtree(f"ABPlayer{arch}{".DEV" if DEV else ""}", ignore_errors=True)
PyInstaller.__main__.run(
    [
        run_file_path,
        "-D",
        f"-n=ABPlayer{arch}{".DEV" if DEV else ""}",
        f"--version-file=version_file",
        "--icon=icon.ico",
        "--distpath=.",
        "--workpath=temp",
        "--specpath=sources",
        "-y",
        "--clean",
        *(("-w",) if not DEV else ()),  # hide consol in not DEV build
        # "--onefile",
        f"--add-data={os.path.join(dev_path, 'web', 'static')};static",
        f"--add-data={os.path.join(dev_path, 'web', 'templates')};templates",
        f"--add-data={os.path.join(dev_path, 'drivers', 'bin')};bin",
        *(
            "--add-data="
            f"{os.path.join(dev_path, 'locales', lang, 'LC_MESSAGES', 'base.mo')};"
            f"locales/{lang}/LC_MESSAGES"
            for lang in locales
        ),
    ]
)
shutil.rmtree("temp")

# returning dev env vars
if not DEV and dev_env_vars:
    with open(main_file_path, encoding="utf-8") as file:
        text = file.read()
    text = text.replace("# DEV\n", f"# DEV\n{dev_env_vars}")
    with open(main_file_path, "w", encoding="utf-8") as file:
        file.write(text)


def get_file_hash(fp: str, hash_func=hashlib.md5) -> str:
    hash_func = hash_func()
    with open(fp, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            hash_func.update(block)
    file_hash = hash_func.hexdigest()
    return file_hash


# SAVING INFO ABOUT CURRENT BUILD
if save_update:
    print("\nSaving update")
    with open(last_build_file_path, encoding="utf-8") as file:
        last_build_version = file.read()
    with open(
        os.path.join(
            "updates",
            last_build_version,
            "x32" if platform.architecture()[0] == "32bit" else "x64",
            "update.json",
        ),
        "rb",
    ) as file:
        last_update = orjson.loads(file.read())
    current_update = {
        "version": str(__version__),
        "arch": "x32" if platform.architecture()[0] == "32bit" else "x64",
        "update": {"remove": [], "new": []},
        "files": {},
    }
    for root, _, file_names in os.walk(f"ABPlayer{arch}"):
        if "__pycache__" in root:
            continue
        for file_name in file_names:
            file_path = os.path.join(root, file_name)
            if root not in current_update["files"]:
                current_update["files"][root] = {}
            current_update["files"][root][file_name] = get_file_hash(file_path)

    # Note files that removed in new version
    for root, files in last_update["files"].items():
        current_update["update"]["remove"].extend(
            [
                os.path.join(root, file_name)
                for file_name in files
                if file_name not in current_update["files"].get(root, {})
            ]
        )
    # Note files that added or changed in new version
    for root, files in current_update["files"].items():
        current_update["update"]["new"].extend(
            [
                os.path.join(root, file_name)
                for file_name, file_hash in files.items()
                if file_hash != last_update["files"].get(root, {}).get(file_name, "")
            ]
        )

    if os.path.exists(update_dir_path):
        shutil.rmtree(update_dir_path)

    for file_path in current_update["update"]["new"]:
        destination_path = Path(os.path.join(update_dir_path, file_path)).parent
        destination_path.mkdir(parents=True, exist_ok=True)
        shutil.copy(file_path, destination_path)

    with open(update_file_path, "w", encoding="utf-8") as file:
        json.dump(current_update, file, indent=4)
    with open(updates_file_path, encoding="utf-8") as file:
        updates_ = orjson.loads(file.read())
    updates = {str(__version__): {}}
    if args.manual:
        updates[str(__version__)]["manual"] = True
    if args.updater:
        updates[str(__version__)]["updater"] = args.updater
    updates.update(updates_)
    with open(updates_file_path, "w", encoding="utf-8") as file:
        json.dump(updates, file, indent=4)
    if __version__.is_stable and args.mark_as_latest:
        # save __version__ as latest if it`s stable version
        with open(last_build_file_path, "w", encoding="utf-8") as file:
            file.write(str(__version__))

    print("Preparing nsis")
    prepare_nsis(current_update, arch)

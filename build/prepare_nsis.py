"""

Prepares NSIS files.

"""

import os


def prepare_nsis(build: dict, arch: str) -> None:
    install = ""

    for root, files in build["files"].items():
        out_path = root.replace("ABPlayer", "$INSTDIR")
        if len(files):
            install += f'\n  SetOutPath "{out_path}"'
        for file_name in files:
            install += f'\n  File "{os.path.join(root, file_name)}"'

    _prepare_file("installer", arch, build["version"], install)
    _prepare_file("updater", arch, build["version"], install)


def _prepare_file(target: str, arch: str, version: str, install: str) -> None:
    with open(f"{target}_template.nsi") as file:
        text = file.read()

    text = text.replace("{arch}", arch)
    text = text.replace(
        "{installdir}", "$PROGRAMFILES32" if arch == " x32" else "$PROGRAMFILES64"
    )
    text = text.replace("{version}", version)
    text = text.replace("{install}", install)

    with open(f"{target}{arch}.nsi", "w") as file:
        file.write(text)

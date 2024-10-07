import os


ADDITIONAL_UNINSTALL = (
    "\n  " + r'RMDir /r "$INSTDIR\ABPlayer.exe.WebView2"'
    "\n"
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\debug.log"'
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\library.sqlite"'
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\config.json"'
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\temp.txt"'
    "\n  " + r'RMDir "$LocalAppData\AudioBookPlayer"'
)


def prepare_nsis(build: dict) -> None:
    install = ""
    uninstall_files = ""
    uninstall_dirs = []

    for root, file_names in build["files"].items():
        out_path = root.replace("ABPlayer", "$INSTDIR")
        if len(file_names):
            install += f'\n  SetOutPath "{out_path}"'
        uninstall_dirs.append(f'  RMDir "{out_path}"')
        for file_name in file_names:
            install += f'\n  File "{os.path.join(root, file_name)}"'
            uninstall_files += f'\n  Delete "{os.path.join(out_path, file_name)}"'

    uninstall_dirs.reverse()
    uninstall = uninstall_files + "\n\n" + "\n".join(uninstall_dirs)
    uninstall += ADDITIONAL_UNINSTALL

    _prepare_file("installer", build["version"], install, uninstall)
    _prepare_file("updater", build["version"], install, uninstall)


def _prepare_file(target: str, version: str, install: str, uninstall: str) -> None:
    with open(f"{target}_template.nsi") as file:
        text = file.read()

    text = text.replace("{version}", version)
    text = text.replace("{install}", install)
    text = text.replace("{uninstall}", uninstall)

    with open(f"{target}", "w") as file:
        file.write(text)

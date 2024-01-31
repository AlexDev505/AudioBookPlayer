import os
import re


ADDITIONAL_UNINSTALL = (
    "\n"
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\debug.log"'
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\library.sqlite"'
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\config.json"'
    "\n  " + r'Delete "$LocalAppData\AudioBookPlayer\temp.txt"'
    "\n  " + r'RMDir "$LocalAppData\AudioBookPlayer"'
)


def prepare_installer(build: dict) -> None:
    with open("installer_template.nsi") as file:
        text = file.read()

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

    text = text.replace("{version}", build["version"])
    text = text.replace("{install}", install)
    text = text.replace("{uninstall}", uninstall)

    with open("installer.nsi", "w") as file:
        file.write(text)


def prepare_updater(
    previous_build: dict, build: dict, update_uninstaller: bool = False
) -> None:
    with open("updater_template.nsi") as file:
        text = file.read()

    install_static = "\n"
    install = ""
    uninstall_files = ""
    uninstall_dirs = []

    for root, file_names in build["files"].items():
        previous_root_files = previous_build["files"].get(root) or []
        out_path = root.replace("ABPlayer", "$INSTDIR")
        uninstall_dirs.append(f'  RMDir "{out_path}"')
        path_added = False
        static_path_added = False
        for file_name in file_names:
            uninstall_files += f'\n  Delete "{os.path.join(out_path, file_name)}"'

            if file_name not in previous_root_files:
                if not path_added:
                    path_added = True
                    install += f'\n    SetOutPath "{out_path}"'
                install += f'\n    File "{os.path.join(root, file_name)}"'
                continue

            if r"\static" in root or r"\templates" in root:
                if not static_path_added:
                    static_path_added = True
                    install_static += f'\n    SetOutPath "{out_path}"'
                install_static += f'\n    File "{os.path.join(root, file_name)}"'

    for root in reversed(previous_build["files"].keys()):
        file_names = previous_build["files"][root]
        current_root_files = build["files"].get(root)
        out_path = root.replace("ABPlayer", "$INSTDIR")
        path_to_remove = not (file_names == current_root_files)
        for file_name in file_names:
            if current_root_files is not None and file_name in current_root_files:
                path_to_remove = False
                continue
            install += f'\n    Delete "{os.path.join(out_path, file_name)}"'
        if path_to_remove:
            install += f'\n    RMDir "{out_path}"'

    text = text.replace("{version}", build["version"])

    if install:
        update_uninstaller = True
        text = text.replace("{install}", install_static + "\n" + install + "\n")
    else:
        text = text.replace("{install}", install_static + "\n")

    if update_uninstaller:
        uninstall_dirs.reverse()
        uninstall = uninstall_files + "\n\n" + "\n".join(uninstall_dirs)
        uninstall += ADDITIONAL_UNINSTALL
        text = text.replace("{uninstall}", uninstall)
        text = text.replace("\n{%uninstaller section%}", "")
        text = text.replace("\n{%uninstaller section end%}", "")
    else:
        text = text.replace("{uninstall}", "")
        text = re.sub(
            r"\s{%uninstaller section%}\s(.*\s)+?{%uninstaller section end%}", "", text
        )

    with open("updater.nsi", "w") as file:
        file.write(text)

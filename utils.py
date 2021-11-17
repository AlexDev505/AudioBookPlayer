import os
import re
import sys

from loguru import logger

logger.remove(0)

logger.add(
    sys.stdout,
    format="<lvl><n>{message}</n></lvl>",
    level=0,
)

EXECUTE = [r"ABPlayer\ui\icons_rc.py"]


def convert(x: int) -> str:
    """
    Конвертирует число битов в другие.
    """

    x /= 1024
    _i = ["Кб", "Мб", "Гб"]
    i = 0
    while x > 1024:
        x /= 1024
        i += 1
    return "{:.2f} {}".format(x, _i[i])


def rows_count(all_info=True):
    """
    Считает файлы и строки.
    :param all_info:
        Для True - выводит информацию по каждому файлу.
        Для False - выводит только итоговую информацию.
    """
    all_files = []
    all_rows = []
    all_sizes = []

    def handle_file(name: str):
        if not name.endswith(".py") or name in EXECUTE:
            return

        size = os.path.getsize(name)
        with open(name, encoding="utf-8") as f:
            rows = len(f.readlines()) + 1

        if all_info:
            logger.opt(colors=True).info(
                f"\t<g>{name}</g>\n"
                f"Кол-во строк: <e>{rows}</e>\n"
                f"Размер: <e>{convert(size)}</e>\n"
            )

        return rows, size

    for dir_name in ["ABPlayer"]:
        for root, dirs, files in os.walk(dir_name):
            for file in files:
                file_path = os.path.join(root, file)
                res = handle_file(file_path)
                if res:
                    all_files.append(file_path)
                    all_rows.append(res[0])
                    all_sizes.append(res[1])

    logger.opt(colors=True).info(
        f"\n\t<g>Итоги</g>\n"
        f"Всего файлов: <e>{len(all_files)}</e>\n"
        f"Всего строк: <e>{sum(all_rows)}</e>\n"
        f"Общий размер: <e>{convert(sum(all_sizes))}</e>\n"
        f"Среднее кол-во строк: <e>{sum(all_rows) // len(all_rows)}</e>\n"
        f"Максимальное кол-во строк: <e>{max(all_rows)}</e> "
        f"(<g>{all_files[all_rows.index(max(all_rows))]}</g>)\n"
    )


def fix_icons(file_path="ABPlayer/ui/main.py") -> None:
    """
    Фиксит размер иконок.
    По умолчанию pyuic добавляет иконки в виде Pixmap,
    из-за этого у иконок не правильный размер.
    """
    with open(file_path, encoding="utf-8") as file:
        text = file.read()

    icons = re.findall(
        r"\s*(icon\S*?) = QtGui.QIcon\(\)\n"
        r'\s*icon\S*?\.addPixmap\(\D*?QtGui.QPixmap\("(\S+?)"\D*?\)\D*?\)',
        text,
        flags=re.MULTILINE,
    )

    text = re.sub(
        rf"\s*icon\S*? = QtGui.QIcon\(\)\n" rf"\s*icon\S*?\.addPixmap\(\D+?\)\n",
        "",
        text,
    )

    for icon in icons:
        text = re.sub(
            rf"(?P<spaces>\s*)(?P<obj>\S+?)\({icon[0]}\)",
            rf'\n\g<spaces>\g<obj>(QtGui.QIcon("{icon[1]}"))',
            text,
        )

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(text)


if __name__ == "__main__":
    # fix_icons("ABPlayer/ui/book.py")
    # fix_icons()
    rows_count(all_info=True)
    pass

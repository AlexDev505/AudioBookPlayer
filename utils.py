import os
import sys

from loguru import logger


logger.remove(0)

logger.add(
    sys.stdout,
    format="<lvl><n>{message}</n></lvl>",
    level=0,
)

EXECUTE = []


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
    all_rows_without_docstrings = []
    all_sizes = []

    def handle_file(name: str):
        if not (name.endswith(".py") or name.endswith(".js")) or name in EXECUTE:
            return

        size = os.path.getsize(name)
        with open(name, encoding="utf-8") as f:
            f_data = list(map(str.strip, f.readlines()))
            rows = len(f_data) + 1

            start_i = -1
            while '"""' in f_data:
                if start_i == -1:
                    start_i = f_data.index('"""')
                    f_data[start_i] = ""
                    if not (start_i == 0 or f_data[start_i - 1].endswith(":")):
                        continue
                else:
                    end_i = f_data.index('"""')
                    f_data[start_i : end_i + 1] = []
                    start_i = -1

            rows_without_docstrings = len(f_data) + 1

        if all_info:
            logger.opt(colors=True).info(
                f"\t<g>{name}</g>\n"
                f"Кол-во строк: <e>{rows}</e>\n"
                f"Кол-во строк (без комментариев): <e>{rows_without_docstrings}</e>\n"
                f"Размер: <e>{convert(size)}</e>\n"
            )

        return rows, rows_without_docstrings, size

    for dir_name in ["ABPlayer"]:
        for root, dirs, files in os.walk(dir_name):
            for file in files:
                file_path = os.path.join(root, file)
                res = handle_file(file_path)
                if res:
                    all_files.append(file_path)
                    all_rows.append(res[0])
                    all_rows_without_docstrings.append(res[1])
                    all_sizes.append(res[2])

    logger.opt(colors=True).info(
        f"\n\t<g>Итоги</g>\n"
        f"Всего файлов: <e>{len(all_files)}</e>\n"
        f"Всего строк: <e>{sum(all_rows)}</e>\n"
        f"Всего строк (без комментариев): <e>{sum(all_rows_without_docstrings)}</e>\n"
        f"Всего строк комментариев: <e>{sum(all_rows) - sum(all_rows_without_docstrings)}</e>\n"
        f"Общий размер: <e>{convert(sum(all_sizes))}</e>\n"
        f"Среднее кол-во строк: <e>{sum(all_rows) // len(all_rows)}</e>\n"
        f"Максимальное кол-во строк: <e>{max(all_rows)}</e> "
        f"(<g>{all_files[all_rows.index(max(all_rows))]}</g>)\n"
        f"Максимальное кол-во строк (без комментариев): "
        f"<e>{max(all_rows_without_docstrings)}</e> (<g>"
        f"{all_files[all_rows_without_docstrings.index(
            max(all_rows_without_docstrings)
        )]}"
        f"</g>)\n"
    )


if __name__ == "__main__":
    rows_count(all_info=True)

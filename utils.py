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
    Converts the number of bits to other units.
    """

    x /= 1024
    _i = ["KB", "MB", "GB"]
    i = 0
    while x > 1024:
        x /= 1024
        i += 1
    return "{:.2f} {}".format(x, _i[i])


def rows_count(all_info=True):
    """
    Counts files and lines.
    :param all_info:
        For True - outputs information for each file.
        For False - outputs only the summary information.
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
                f"Number of lines: <e>{rows}</e>\n"
                f"Number of lines (without comments): <e>{rows_without_docstrings}</e>\n"
                f"Size: <e>{convert(size)}</e>\n"
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
        f"\n\t<g>Summary</g>\n"
        f"Total files: <e>{len(all_files)}</e>\n"
        f"Total lines: <e>{sum(all_rows)}</e>\n"
        f"Total lines: (without comments): <e>{sum(all_rows_without_docstrings)}</e>\n"
        f"Total lines: comments: <e>{sum(all_rows) - sum(all_rows_without_docstrings)}</e>\n"
        f"Total size: <e>{convert(sum(all_sizes))}</e>\n"
        f"Average number of lines: <e>{sum(all_rows) // len(all_rows)}</e>\n"
        f"Maximum number of lines: <e>{max(all_rows)}</e> "
        f"(<g>{all_files[all_rows.index(max(all_rows))]}</g>)\n"
        f"Maximum number of lines: (without comments): "
        f"<e>{max(all_rows_without_docstrings)}</e> (<g>"
        f"{all_files[all_rows_without_docstrings.index(
            max(all_rows_without_docstrings)
        )]}"
        f"</g>)\n"
    )


if __name__ == "__main__":
    rows_count(all_info=True)

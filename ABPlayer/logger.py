import dataclasses
import os
import sys

from loguru import logger

import temp_file

# Удаление настроек логгера по умолчанию
logger.remove(0)


@dataclasses.dataclass
class LoggingLevel:
    """
    Вспомогательный класс для фильтрации
    логов по их уровню.
    """

    level: str

    def __call__(self, record: dict) -> bool:
        level_no = logger.level(self.level).no
        return record["level"].no >= level_no


def update_logging_level(level: str) -> None:
    """
    Обновляет уровень логов логгера.
    :param level: Новый уровень для логов.
    """
    level_handler.level = level


def formatter(record) -> str:
    record["extra"]["VERSION"] = os.environ["VERSION"]
    return (
        "<lvl><n>[{level.name} </n></lvl>"
        "<g>{time:YYYY-MM-DD HH:mm:ss.SSS}</g> "
        "<lg>v{extra[VERSION]}</lg>"
        "<lvl><n>]</n></lvl> "
        "<w>{thread.name}:{module}.{function}</w>: "
        "<lvl><n>{message}</n></lvl>\n{exception}"
    )


# Считываем уровень логирования(по умолчанию DEBUG)
logging_level = temp_file.load().get("logging_level") or "DEBUG"
if logging_level not in {"TRACE", "DEBUG", "INFO"}:
    logging_level = "DEBUG"
    temp_file.delete_items("logging_level")
level_handler = LoggingLevel(logging_level)

if os.environ.get("CONSOLE"):
    console_logger_handler = logger.add(
        sys.stdout,
        colorize=True,
        format=formatter,
        filter=level_handler,
        level=0,
    )

file_logger_handler = logger.add(
    os.environ["DEBUG_PATH"],
    colorize=False,
    format=formatter,
    filter=level_handler,
    level=0,
)

logger.level("TRACE", color="<w>")
logger.level("INFO", color="<c>")

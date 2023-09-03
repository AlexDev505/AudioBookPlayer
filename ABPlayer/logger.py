import os
import sys

from loguru import logger


try:  # Удаление настроек логгера по умолчанию
    logger.remove(0)
except ValueError:
    pass


def formatter(record) -> str:
    record["extra"]["VERSION"] = os.environ.get("VERSION", "0")
    return (
        "<lvl><n>[{level.name} </n></lvl>"
        "<g>{time:YYYY-MM-DD HH:mm:ss.SSS}</g> "
        "<lg>v{extra[VERSION]}</lg>"
        "<lvl><n>]</n></lvl> "
        "<w>{thread.name}:{module}.{function}</w>: "
        "<lvl><n>{message}</n></lvl>\n{exception}"
    )


LOGGING_LEVEL = os.environ.get("LOGGING_LEVEL", "DEBUG")
if os.environ.get("CONSOLE"):
    console_logger_handler = logger.add(
        sys.stdout, colorize=True, format=formatter, level=LOGGING_LEVEL
    )

if DEBUG_PATH := os.environ.get("DEBUG_PATH"):
    file_logger_handler = logger.add(
        DEBUG_PATH, colorize=False, format=formatter, level=LOGGING_LEVEL
    )

logger.level("TRACE", color="<lk>")  # TRACE - синий
logger.level("DEBUG", color="<w>")  # DEBUG - белый
logger.level("INFO", color="<c><bold>")  # INFO - бирюзовый

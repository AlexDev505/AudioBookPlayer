from __future__ import annotations

import typing as ty

import orjson
from loguru import logger
from websockets.exceptions import ConnectionClosedOK

from .exceptions import DownloaderError, IncorrectMessage, UnknownCommand

if ty.TYPE_CHECKING:
    from websockets import ServerConnection


async def ws_handler(websocket: ServerConnection):
    logger.opt(colors=True).debug(f"New client: <r>{websocket.id}</r>")
    try:
        async for message in websocket:
            data = orjson.loads(message)
            assert type(data) is dict
            assert "command" in data
            await handle_command(websocket, data)
    except (orjson.JSONDecodeError, AssertionError):
        await error(websocket, IncorrectMessage())
    except ConnectionClosedOK:
        pass
    finally:
        logger.opt(colors=True).debug(
            f"Client disconnected: <r>{websocket.id}</r>"
        )


async def handle_command(
    websocket: ServerConnection, command: dict[str, ty.Any]
):
    match command["command"]:
        case "ping":
            await websocket.send("pong")
        case "add_book":
            await add_book(websocket, command)
        case _:
            await error(websocket, UnknownCommand())


async def add_book(websocket: ServerConnection, command: dict[str, ty.Any]):
    pass


async def error(websocket: ServerConnection, exc: DownloaderError):
    await send(websocket, "error", code=exc.code, message=exc.message)
    logger.opt(colors=True).debug(
        f"<r>{websocket.id}</r> raises error: <bold>{type(exc).__name__}: {exc}</bold>"
    )


async def send(
    websocket: ServerConnection, event_type: str, **data: ty.Any
) -> None:
    event = dict(type=event_type, **data)
    await websocket.send(orjson.dumps(event))

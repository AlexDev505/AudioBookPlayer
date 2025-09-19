from __future__ import annotations

import http
import typing as ty

from loguru import logger
from websockets import Headers, Response

if ty.TYPE_CHECKING:
    from websockets import Request, ServerConnection


async def http_handler(
    connection: ServerConnection, request: Request
) -> Response:
    if request.path == "/healthz":
        return Response(
            http.HTTPStatus.OK,
            "OK",
            Headers({"Access-Control-Allow-Origin": "*"}),
            b"OK\n",
        )
    return Response(http.HTTPStatus.BAD_REQUEST, "Bad Request", Headers())

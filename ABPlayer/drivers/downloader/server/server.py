import asyncio

from loguru import logger
from websockets.asyncio.server import serve

from .downloader import run_next
from .http_handler import http_handler
from .ws_handler import ws_handler


async def main():
    asyncio.create_task(run_next())
    async with serve(
        ws_handler, "localhost", 8765, process_request=http_handler
    ) as server:
        logger.info("Server started")
        await server.serve_forever()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    finally:
        logger.info("Server stopped")

from __future__ import annotations

import asyncio
import typing as ty

if ty.TYPE_CHECKING:
    from models.book import Book


queue: asyncio.Queue[Book] = asyncio.Queue(5)


async def add_book(book: Book):
    await queue.put(book)


async def run_next():
    book = await queue.get()

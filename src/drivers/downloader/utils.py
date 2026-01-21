from __future__ import annotations

import typing as ty

if ty.TYPE_CHECKING:
    from models.book import SourceType


def get_downloading_id(sid: int, stype: SourceType) -> str:
    return f"{stype.name}-{sid}"

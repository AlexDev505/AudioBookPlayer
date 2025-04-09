import re
import time
from functools import wraps, lru_cache


def ttl_cache(max_age: int, maxsize: int = 128, typed: bool = False):
    """
    A decorator that caches the result of a function call
    for a specified period of time.
    max_age: Duration to keep the cache (in seconds).
    """

    def _decorator(fn):
        @lru_cache(maxsize, typed)
        def _new(*args, __time, **kwargs):
            return fn(*args, **kwargs)

        @wraps(fn)
        def _wrapper(*args, **kwargs):
            return _new(*args, **kwargs, __time=int(time.time() / max_age))

        return _wrapper

    return _decorator


def duration_str_to_sec(duration: str) -> int:
    for pattern in [
        r"(((?P<h>\d+):)?(?P<m>\d{1,2}):)?(?P<s>\d{1,2})?",
        r"((?P<h>\d+) час(а|ов)?)?\s?((?P<m>\d{1,2}) минут[аы]?)?(?P<s>)",
        r"((?P<h>\d+) ч\.)?\s?((?P<m>\d{1,2}) мин\.)?(?P<s>)",
    ]:
        if match := re.fullmatch(pattern, duration):
            if sec := (
                int(match.group("h") or 0) * 3600
                + int(match.group("m") or 0) * 60
                + int(match.group("s") or 0)
            ):
                return sec
    raise ValueError(f"Invalid duration: {duration}")


def duration_sec_to_str(sec: int) -> str:
    h, m, s = sec // 3600, sec % 3600 // 60, sec % 60
    return (
        f"{f"{h}:" if h else ""}"
        f"{f"{str(m).rjust(2, "0") if h else m}:" if m else ("00:" if h else "")}"
        f"{(str(s).rjust(2, "0") if m or h else s) if s else ("00" if m or h else "")}"
    )

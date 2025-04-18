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

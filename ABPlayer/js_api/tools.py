import time
from functools import wraps, lru_cache


def ttl_cache(max_age: int, maxsize: int = 128, typed: bool = False):
    """
    Декоратор кэширующий результат вызова функции
    в течении определенного промежутка времени.
    max_age: Продолжительность сохранения кэша(в секундах).
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


"""

Исключения, возникающие при загрузке приложения.

"""

from __future__ import annotations

import typing as ty
from inspect import isfunction


class DriverError(Exception):
    """
    Базовый класс исключения.
    """

    def to_dict(self) -> ty.Dict[str, ty.Any]:
        """
        Конвертирует исключение в словарь
        для дальнейшего отображения ошибки в приложении.
        """
        return {
            k: (self.__getattribute__(k) if isfunction(v) else v)
            for k, v in vars(self.__class__).items()
            if not k.startswith("_")
        }


class DownloadingFail(DriverError):
    text = "Ошибка при загрузке драйвера.\nПовторите позже."


__all__ = [
    "DriverError",
    "DownloadingFail",
]

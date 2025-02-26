from __future__ import annotations

import dataclasses
import sqlite3
import types as tys
import typing as ty
from contextlib import suppress
from datetime import datetime
from enum import Enum
from inspect import isclass

import orjson
from loguru import logger

from models.book import DATETIME_FORMAT


SQL_TYPES = {
    "str": "TEXT",
    "int": "INTEGER",
    "float": "REAL",
    "datetime": "datetime",
}


def adapt_json(obj: ty.Any) -> bytes:
    return orjson.dumps(obj)


@logger.catch
def convert_json(obj: bytes) -> ty.Any:
    return orjson.loads(obj)


sqlite3.register_adapter(dict, adapt_json)
sqlite3.register_adapter(list, adapt_json)
sqlite3.register_converter("json", convert_json)


def adapt_datetime(obj: datetime) -> bytes:
    return obj.strftime(DATETIME_FORMAT).encode()


def convert_datetime(obj: bytes) -> datetime:
    return datetime.strptime(obj.decode("utf-8"), DATETIME_FORMAT)


sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("datetime", convert_datetime)


@dataclasses.dataclass
class Field:
    field_name: str
    sql_type: str
    python_type: ty.Type


class UnionType:
    def __init__(self, *args: ty.Any):
        self.types = list(args)
        if None in self.types:
            self.types.remove(None)

    def __call__(self, obj: ty.Any) -> ty.Any:
        for type_ in self.types:
            try:
                return type_(obj)
            except (ValueError, TypeError):
                pass


def get_signature(model) -> dict[str, Field]:
    signature = {}
    for field_name, field_type in ty.get_type_hints(model).items():
        if ty.get_origin(field_type) in {ty.Union, tys.UnionType}:
            field_type = UnionType(*ty.get_args(field_type))
        field_type_name = (
            field_type.__name__.lower()
            if isclass(field_type)
            else field_type.__class__.__name__.lower()
        )
        sql_type = SQL_TYPES.get(field_type_name)
        if isclass(field_type):
            if issubclass(field_type, Enum):
                sql_type = SQL_TYPES["str"]
        if not sql_type:
            sql_type = "json"
        signature[field_name] = Field(field_name, sql_type, field_type)
    return signature


def convert_value(field: Field, obj: ty.Any) -> ty.Any:
    if type(obj) == field.python_type:
        return obj

    with suppress(ValueError, TypeError):
        if dataclasses.is_dataclass(field.python_type):
            if type(obj) is dict:
                return field.python_type(**obj)
            return field.python_type(*obj)
        return field.python_type(obj)


def adapt_value(obj: ty.Any) -> ty.Any:
    if isinstance(obj, Enum):
        return obj.value
    elif dataclasses.is_dataclass(obj):
        return dataclasses.asdict(obj)
    elif isinstance(obj, dict) and type(obj) is not dict:
        return dict(obj)
    elif isinstance(obj, list) and type(obj) is not list:
        return list(obj)
    return obj


__all__ = ["get_signature", "convert_value", "adapt_value", "Field"]


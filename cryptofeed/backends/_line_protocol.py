'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import math
from decimal import Decimal


QUESTDB = 'questdb'
INFLUXDB = 'influxdb'
_DIALECTS = (QUESTDB, INFLUXDB)


class TimestampMicros(int):
    __slots__ = ()


def _escape_key(value: str, *, backslash: bool = True) -> str:
    if backslash:
        value = value.replace('\\', '\\\\')
    return (value.replace('\n', ' ').replace('\r', ' ').replace(',', '\\,').replace('=', '\\=').replace(' ', '\\ '))


def _escape_measurement(value: str, *, backslash: bool = True) -> str:
    if backslash:
        value = value.replace('\\', '\\\\')
    return (value.replace('\n', ' ').replace('\r', ' ').replace(',', '\\,').replace(' ', '\\ '))


def _escape_string_field(value: str) -> str:
    return (value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' '))


def _renderable(value) -> bool:
    if value is None:
        return False
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, Decimal):
        return value.is_finite()
    return True


def _render_field(value, *, int_suffix: bool = True) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, TimestampMicros):
        return f'{int(value)}t' if int_suffix else str(int(value))
    if isinstance(value, int):
        return f'{value}i' if int_suffix else str(value)
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, Decimal):
        return format(value, 'f')
    if isinstance(value, str):
        return f'"{_escape_string_field(value)}"'
    raise TypeError(f'cannot render {type(value).__name__} as a line-protocol field: {value!r}')


def encode(measurement: str, tags: dict, fields: dict, timestamp: int, *, dialect: str = QUESTDB) -> str:
    if dialect not in _DIALECTS:
        raise ValueError(f'unknown line protocol dialect {dialect!r}, expected one of {_DIALECTS}')
    backslash = dialect != INFLUXDB
    int_suffix = dialect != INFLUXDB

    parts = [_escape_measurement(measurement, backslash=backslash)]
    for key, value in tags.items():
        if value is None:
            continue
        escaped_key = _escape_key(key, backslash=backslash)
        escaped_value = _escape_key(str(value), backslash=backslash)
        if not escaped_key or not escaped_value:
            continue
        parts.append(f'{escaped_key}={escaped_value}')
    field_parts = [f'{_escape_key(key, backslash=backslash)}={_render_field(value, int_suffix=int_suffix)}'
                   for key, value in fields.items() if _renderable(value)]
    if not field_parts:
        return ''
    return f'{",".join(parts)} {",".join(field_parts)} {timestamp}'

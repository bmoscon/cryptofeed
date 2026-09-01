'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''


_SECONDS = {
    '10s': 10,
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '10m': 600,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    '2h': 7200,
    '3h': 10800,
    '4h': 14400,
    '6h': 21600,
    '8h': 28800,
    '12h': 43200,
    '1d': 86400,
    '3d': 259200,
    '1w': 604800,
    '2w': 1209600,
    '15d': 1296000,
    '1M': 2592000,
    '1Y': 31536000,
}


def timedelta_str_to_sec(td: str) -> int:
    try:
        return _SECONDS[td]
    except KeyError:
        raise ValueError(f'unknown candle interval {td!r}. Must be one of {", ".join(sorted(_SECONDS))}') from None

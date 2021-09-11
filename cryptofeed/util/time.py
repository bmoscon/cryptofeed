'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''


def timedelta_str_to_sec(td: str):
    if td == '1m':
        return 60
    if td == '3m':
        return 180
    if td == '5m':
        return 300
    if td == '10m':
        return 600
    if td == '15m':
        return 900
    if td == '30m':
        return 1800
    if td == '1h':
        return 3600
    if td == '2h':
        return 7200
    if td == '4h':
        return 14400
    if td == '6h':
        return 21600
    if td == '8h':
        return 28800
    if td == '12h':
        return 43200
    if td == '1d':
        return 86400
    if td == '3d':
        return 259200
    if td == '1w':
        return 604800
    if td == '1M':
        return 2592000
    if td == '1Y':
        return 31536000

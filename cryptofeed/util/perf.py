'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


This file contains helper functions for performance instrumentation
'''
import time
from collections import defaultdict


_perf_data = defaultdict(lambda: defaultdict(dict))
_perf_stats = defaultdict(list)


def perf_start(exchange: str, key: str):
    _perf_data[exchange][key]['start'] = time.time()


def perf_end(exchange: str, key: str):
    _perf_data[exchange][key]['end'] = time.time()
    _perf_stats[f"{exchange}-{key}"].append(_perf_data[exchange][key]['end'] - _perf_data[exchange][key]['start'])


def perf_log(exchange: str, key: str, stats=1000, stats_only=True):
    if not stats_only:
        print("{}: {} - {:.2f} ms".format(exchange, key, 1000 * (_perf_data[exchange][key]['end'] - _perf_data[exchange][key]['start'])))
    if stats and len(_perf_stats[f"{exchange}-{key}"]) > stats:
        stats_key = f"{exchange}-{key}"
        print(f"For last {stats} executions:")
        _min = min(_perf_stats[stats_key]) * 1000
        _max = max(_perf_stats[stats_key]) * 1000
        _avg = sum(_perf_stats[stats_key]) / len(_perf_stats[stats_key]) * 1000
        print(f"   Min: {_min} ms")
        print(f"   Max: {_max} ms")
        print(f"   Average: {_avg} ms")
        _perf_stats[stats_key] = []

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from typing import Dict, Tuple


class _Symbols:
    def __init__(self):
        self.data = {}

    def clear(self):
        self.data = {}

    def set(self, exchange: str, normalized: dict, exchange_info: dict):
        self.data[exchange] = {}
        self.data[exchange]['normalized'] = normalized
        self.data[exchange]['info'] = exchange_info

    def get(self, exchange: str) -> Tuple[Dict, Dict]:
        return self.data[exchange]['normalized'], self.data[exchange]['info']

    def populated(self, exchange: str) -> bool:
        return exchange in self.data


Symbols = _Symbols()

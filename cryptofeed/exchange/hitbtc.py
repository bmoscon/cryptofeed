'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from typing import Dict, Tuple

from cryptofeed.defines import HITBTC
from cryptofeed.exchanges import Bequant

LOG = logging.getLogger('feedhandler')


class HitBTC(Bequant):
    id = HITBTC
    symbol_endpoint = 'https://api.hitbtc.com/api/2/public/symbol'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        normalized_currencies = {
            'USD': 'USDT',
            'USDB': 'USD',
        }

        for symbol in data:
            base_currency = normalized_currencies[symbol['baseCurrency']] if symbol['baseCurrency'] in normalized_currencies else symbol['baseCurrency']
            quote_currency = normalized_currencies[symbol['quoteCurrency']] if symbol['quoteCurrency'] in normalized_currencies else symbol['quoteCurrency']
            normalized = f"{base_currency}{symbol_separator}{quote_currency}"
            ret[normalized] = symbol['id']
            info['tick_size'][normalized] = symbol['tickSize']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.address = {
            'market': 'wss://api.hitbtc.com/api/2/ws/public',
            'trading': 'wss://api.hitbtc.com/api/2/ws/trading',
            'account': 'wss://api.hitbtc.com/api/2/ws/account',
        }

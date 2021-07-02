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

try:
    from icecream import ic
except ImportError:  # Graceful fallback when IceCream isn't installed in production
    ic = lambda *a: None if not a else (a[0] if len(a) == 1 else a)  # noqa

class HitBTC(Bequant):
    id = HITBTC
    symbol_endpoint = 'https://api.hitbtc.com/api/2/public/symbol'
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '4h', '1d', '7d', '1M'}

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
        urls = {
            'market': 'wss://api.hitbtc.com/api/2/ws/public',
            'trading': 'wss://api.hitbtc.com/api/2/ws/trading',
            'account': 'wss://api.hitbtc.com/api/2/ws/account',
        }
        super().__init__(candle_interval='1m')
        super(Bequant, self).__init__(urls, **kwargs)

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from typing import Dict, Tuple

from cryptofeed.defines import BITCOINCOM
from cryptofeed.exchanges import Bequant
from cryptofeed.symbols import Symbol

LOG = logging.getLogger('feedhandler')


class BitcoinCom(Bequant):
    id = BITCOINCOM
    symbol_endpoint = 'https://api.exchange.bitcoin.com/api/2/public/symbol'

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        normalized_currencies = {
            'USD': 'USDT',
        }

        for symbol in data:
            base_currency = normalized_currencies[symbol['baseCurrency']] if symbol['baseCurrency'] in normalized_currencies else symbol['baseCurrency']
            quote_currency = normalized_currencies[symbol['quoteCurrency']] if symbol['quoteCurrency'] in normalized_currencies else symbol['quoteCurrency']
            s = Symbol(base_currency, quote_currency)
            ret[s.normalized] = symbol['id']
            info['tick_size'][s.normalized] = symbol['tickSize']
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.address = {
            'market': 'wss://api.exchange.bitcoin.com/api/2/ws/public',
            'trading': 'wss://api.exchange.bitcoin.com/api/2/ws/trading',
            'account': 'wss://api.exchange.bitcoin.com/api/2/ws/account',
        }

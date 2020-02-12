'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import OKEX
from cryptofeed.exchange.okcoin import OKCoin

import requests


class OKEx(OKCoin):
    """
    OKEx has the same api as OKCoin, just a different websocket endpoint
    """
    id = OKEX
    api = 'https://www.okex.com/api/'
    table_prefixs = ['futures', 'swap', "spot"]

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.address = 'wss://real.okex.com:8443/ws/v3'
        self.book_depth = 200


    @staticmethod
    def get_active_symbols_info():
        return requests.get(OKEx.api + 'futures/v3/instruments').json()


    @staticmethod
    def get_active_symbols():
        symbols = []
        for data in OKEx.get_active_symbols_info():
            symbols.append(data['instrument_id'])
        return symbols

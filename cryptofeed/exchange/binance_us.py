'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.defines import BINANCE_US
from cryptofeed.exchange.binance import Binance


LOG = logging.getLogger('feedhandler')


class BinanceUS(Binance):
    id = BINANCE_US

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # overwrite values previously set by the super class Binance
        self.ws_endpoint = 'wss://stream.binance.us:9443'
        self.rest_endpoint = 'https://api.binance.us/api/v1'
        self.address = self._address()

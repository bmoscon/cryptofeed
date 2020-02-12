'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.defines import BINANCE_JERSEY
from cryptofeed.exchange.binance import Binance


LOG = logging.getLogger('feedhandler')


class BinanceJersey(Binance):
    id = BINANCE_JERSEY

    def __init__(self, pairs=None, channels=None, callbacks=None, depth=1000, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, depth=depth, **kwargs)
        self.ws_endpoint = 'wss://stream.binance.je:9443'
        self.rest_endpoint = 'https://api.binance.je/api/v1'
        self.address = self._address()

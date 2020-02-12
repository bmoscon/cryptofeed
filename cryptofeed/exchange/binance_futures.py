'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.defines import BINANCE_FUTURES
from cryptofeed.exchange.binance import Binance


LOG = logging.getLogger('feedhandler')


class BinanceFutures(Binance):
    id = BINANCE_FUTURES

    def __init__(self, pairs=None, channels=None, callbacks=None, depth=1000, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, depth=depth, **kwargs)
        self.ws_endpoint = 'wss://fstream.binance.com'
        self.rest_endpoint = 'https://fapi.binance.com/fapi/v1'
        self.address = self._address()

    def _check_update_id(self, pair: str, msg: dict):
        skip_update = False
        forced = False

        if pair in self.last_update_id:
            if msg['u'] < self.last_update_id[pair]:
                skip_update = True
            elif msg['U'] <= self.last_update_id[pair] <= msg['u']:
                del self.last_update_id[pair]
                forced = True
            else:
                raise Exception("Error - snaphot has no overlap with first update")

        return skip_update, forced

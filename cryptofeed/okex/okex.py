'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.defines import OKEX
from cryptofeed.okcoin.okcoin import OKCoin


class OKEx(OKCoin):
    """
    OKEx has the same api as OKCoin, just a different websocket endpoint
    """
    id = OKEX
    table_prefixs = ['swap', "spot"]

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.address = 'wss://real.okex.com:10442/ws/v3'
        self.book_depth = 200

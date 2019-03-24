'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
import zlib

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, TICKER, L2_BOOK, OKEX
from cryptofeed.standards import pair_exchange_to_std
from cryptofeed.okcoin.okcoin import OKCoin


LOG = logging.getLogger('feedhandler')


class OKEx(OKCoin):
    """
    OKEx has the same api as OKCoin, just a different websocket endpoint
    """
    id = OKEX

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.address = 'wss://real.okex.com:10442/ws/v3'
        self.book_depth = 200

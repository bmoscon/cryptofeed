'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.defines import FTX_US, L2_BOOK, ORDER_INFO, TICKER, TRADES, FILLS
from cryptofeed.exchanges.ftx import FTX
from cryptofeed.exchanges.mixins.ftx_rest_us import FTXUSRestMixin


LOG = logging.getLogger('feedhandler')


class FTXUS(FTX, FTXUSRestMixin):
    id = FTX_US
    symbol_endpoint = 'https://ftx.us/api/markets'
    websocket_channels = {
        L2_BOOK: 'orderbook',
        TRADES: 'trades',
        TICKER: 'ticker',
        ORDER_INFO: 'orders',
        FILLS: 'fills',
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.address = 'wss://ftx.us/ws/'

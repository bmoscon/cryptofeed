'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.exchanges.mixins.ftx_rest import FTXRestMixin
from cryptofeed.defines import CANCEL_ORDER, L2_BOOK, ORDER_INFO, ORDER_STATUS, PLACE_ORDER, TICKER, TRADES, TRADE_HISTORY


class FTXUSRestMixin(FTXRestMixin):
    api = "https://ftx.us/api"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, ORDER_INFO, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, TRADE_HISTORY
    )

    def funding_sync(self, symbol: str, **kwargs):
        raise NotImplementedError

    async def funding(self, symbol: str, **kwargs):
        raise NotImplementedError

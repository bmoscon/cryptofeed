'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.exchange import RestExchange
from cryptofeed.defines import BUY, SELL, TRADES, L2_BOOK
from cryptofeed.types import OrderBook


LOG = logging.getLogger('feedhandler')


class dYdXRestMixin(RestExchange):
    api = "https://api.dydx.exchange"
    sandbox_api = "https://api.stage.dydx.exchange"
    rest_channels = (
        TRADES, L2_BOOK
    )

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        ret = OrderBook(self.id, symbol)
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self.http_conn.read(f"{self.api}/v3/orderbook/{sym}", retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(data, parse_float=Decimal)
        ret.book.bids = {Decimal(entry['price']): Decimal(entry['size']) for entry in data['bids']}
        ret.book.asks = {Decimal(entry['price']): Decimal(entry['size']) for entry in data['asks']}
        return ret

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        endpoint = f"{self.api}/v3/trades/{sym}?limit=100"

        ret = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
        ret = json.loads(ret, parse_float=Decimal)
        yield self._trade_normalization(symbol, ret)

    def _trade_normalization(self, symbol: str, data: dict):
        def norm(entry):
            return {
                'timestamp': entry['createdAt'].timestamp(),
                'symbol': symbol,
                'id': None,
                'feed': self.id,
                'side': SELL if entry['side'] == 'SELL' else BUY,
                'amount': Decimal(entry['size']),
                'price': Decimal(entry['price']),
            }
        return list(map(norm, data['trades']))

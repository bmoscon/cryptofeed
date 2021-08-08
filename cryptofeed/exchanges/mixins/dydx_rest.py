'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
from datetime import datetime as dt

from yapic import json
from sortedcontainers.sorteddict import SortedDict as sd

from cryptofeed.exchange import RestExchange
from cryptofeed.defines import ASK, BID, BUY, SELL, TRADES, L2_BOOK


LOG = logging.getLogger('feedhandler')


class dYdXRestMixin(RestExchange):
    api = "https://api.dydx.exchange"
    sandbox_api = "https://api.stage.dydx.exchange"
    rest_channels = (
        TRADES, L2_BOOK
    )   

    async def l2_book(self, symbol: str, retry_count=None, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self.http_conn.read(f"{self.api}/v3/orderbook/{sym}", retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(data, parse_float=Decimal)
        return {
            BID: sd({
                Decimal(entry['price']): Decimal(entry['size']) for entry in data['bids']
            }),
            ASK: sd({
                Decimal(entry['price']): Decimal(entry['size']) for entry in data['asks']
            })
        }        

    async def trades(self, symbol: str, start=None, end=None, retry_count=None, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        start, end = self._interval_normalize(start, end)

        base_endpoint = f"{self.api}/v3/trades/{sym}?limit=100"
        endpoint = None

        while True:
            if start and end:
                endpoint = f"{base_endpoint}&startingBeforeOrAt={dt.fromtimestamp(end).isoformat()}Z"

            ret = await self.http_conn.read(endpoint if endpoint else base_endpoint, retry_count=retry_count, retry_delay=retry_delay)
            ret = json.loads(ret, parse_float=Decimal)

            ret = self._trade_normalization(symbol, ret)
            yield ret

            if ret:
                end = ret[-1]['timestamp']
            if not start or end <= start or not ret:
                break
            await asyncio.sleep(1 / self.request_limit)

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

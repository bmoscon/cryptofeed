'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.defines import BUY, L2_BOOK, SELL, TRADES
from cryptofeed.exchange import RestExchange
from cryptofeed.types import OrderBook


LOG = logging.getLogger('feedhandler')


class DeribitRestMixin(RestExchange):
    api = "https://www.deribit.com/api/v2/public/"
    sandbox_api = 'https://test.deribit.com/api/v2/public/'
    rest_channels = (TRADES, L2_BOOK)

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        start, end = self._interval_normalize(start, end)
        if start:
            start = int(start * 1000)
            end = int(end * 1000)

        while True:
            endpoint = f"{self.api}get_last_trades_by_instrument?instrument_name={symbol}&include_old=true&count=1000"
            if start and end:
                endpoint = f"{self.api}get_last_trades_by_instrument_and_time?&start_timestamp={start}&end_timestamp={end}&instrument_name={symbol}&include_old=true&count=1000"

            data = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
            data = json.loads(data, parse_float=Decimal)["result"]["trades"]

            if data:
                if data[-1]["timestamp"] == start:
                    LOG.warning("%s: number of trades exceeds exchange time window, some data will not be retrieved for time %d", self.id, start)
                    start += 1
                else:
                    start = data[-1]["timestamp"]

            orig_data = data
            data = [self._trade_normalization(x) for x in data]
            yield data

            if len(orig_data) < 1000 or not start or not end:
                break
            await asyncio.sleep(1 / self.request_limit)

    def _trade_normalization(self, trade: list) -> dict:

        ret = {
            'timestamp': self.timestamp_normalize(trade["timestamp"]),
            'symbol': self.exchange_symbol_to_std_symbol(trade["instrument_name"]),
            'id': int(trade["trade_id"]),
            'feed': self.id,
            'side': BUY if trade["direction"] == 'buy' else SELL,
            'amount': Decimal(trade["amount"]),
            'price': Decimal(trade["price"]),
        }
        return ret

    async def l2_book(self, symbol: str, retry_count=0, retry_delay=60):
        ret = OrderBook(self.id, symbol)
        symbol = self.std_symbol_to_exchange_symbol(symbol)

        data = await self.http_conn.read(f"{self.api}get_order_book?depth=10000&instrument_name={symbol}", retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(data, parse_float=Decimal)
        for side in ('bids', 'asks'):
            for entry_bid in data["result"][side]:
                price, amount = entry_bid
                ret.book[side][price] = amount
        return ret

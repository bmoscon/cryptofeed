'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.defines import BUY, FUNDING, L2_BOOK, TICKER, TRADES
from cryptofeed.defines import SELL
from cryptofeed.exchange import RestExchange
from cryptofeed.types import OrderBook


LOG = logging.getLogger('cryptofeed.rest')


class FTXRestMixin(RestExchange):
    api = "https://ftx.com/api"
    rest_channels = (
        TRADES, TICKER, L2_BOOK, FUNDING
    )

    async def ticker(self, symbol: str, retry_count=1, retry_delay=60):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self.http_conn.read(f"{self.api}/markets/{sym}", retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(data, parse_float=Decimal)['result']

        return {'symbol': symbol,
                'feed': self.id,
                'bid': data['bid'],
                'ask': data['ask']
                }

    async def l2_book(self, symbol: str, retry_count=1, retry_delay=60):
        ret = OrderBook(self.id, symbol)
        sym = self.std_symbol_to_exchange_symbol(symbol)
        data = await self.http_conn.read(f"{self.api}/markets/{sym}/orderbook?depth=100", retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(data, parse_float=Decimal)['result']
        ret.book.bids = {u[0]: u[1] for u in data['bids']}
        ret.book.asks = {u[0]: u[1] for u in data['asks']}
        return ret

    async def trades(self, symbol: str, start=None, end=None, retry_count=1, retry_delay=10):
        symbol = self.std_symbol_to_exchange_symbol(symbol)
        last = []
        start, end = self._interval_normalize(start, end)

        while True:
            endpoint = f"{self.api}/markets/{symbol}/trades"
            if start and end:
                endpoint = f"{self.api}/markets/{symbol}/trades?start_time={start}&end_time={end}"

            r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
            data = json.loads(r, parse_float=Decimal)['result']

            orig_data = list(data)
            data = self._dedupe(data, last)
            last = list(orig_data)

            data = [self._trade_normalization(x, symbol) for x in data]
            yield data

            if len(orig_data) < 5000:
                break
            end = int(data[-1]['timestamp'])
            await asyncio.sleep(1 / self.request_limit)

    async def funding(self, symbol: str, retry_count=1, retry_delay=10):
        sym = self.std_symbol_to_exchange_symbol(symbol)
        endpoint = f"{self.api}/funding_rates?future={sym}"
        r = await self.http_conn.read(endpoint, retry_count=retry_count, retry_delay=retry_delay)
        data = json.loads(r, parse_float=Decimal)['result']
        data = [self._funding_normalization(x) for x in data]
        return data

    @staticmethod
    def _dedupe(data, last):
        if len(last) == 0:
            return data

        ids = set([data['id'] for data in last])
        ret = []

        for d in data:
            if d['id'] in ids:
                continue
            ids.add(d['id'])
            ret.append(d)

        return ret

    def _trade_normalization(self, trade: dict, symbol: str) -> dict:
        return {
            'timestamp': trade['time'].timestamp(),
            'symbol': self.exchange_symbol_to_std_symbol(symbol),
            'id': trade['id'],
            'feed': self.id,
            'side': SELL if trade['side'] == 'sell' else BUY,
            'amount': trade['size'],
            'price': trade['price']
        }

    def _funding_normalization(self, funding: dict) -> dict:
        return {
            'symbol': self.exchange_symbol_to_std_symbol(funding['future']),
            'feed': self.id,
            'rate': funding['rate'],
            'timestamp': funding['time'].timestamp(),
        }

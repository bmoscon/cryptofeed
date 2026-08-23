'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Tuple

from cryptofeed import _json as json
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BUY, HYPERLIQUID, L1_BOOK, L2_BOOK, PERPETUAL, SELL, SPOT, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import L1Book, OrderBook, Trade


LOG = logging.getLogger(__name__)


class Hyperliquid(Feed):
    id = HYPERLIQUID
    keepalive_interval = 30.0

    async def keepalive(self, conn: AsyncConnection):
        await conn.write(json.dumps({'method': 'ping'}))

    book_delivery = 'snapshot'
    provides_sequence_number = False
    provides_checksum = False
    websocket_endpoints = [WebsocketEndpoint('wss://api.hyperliquid.xyz/ws')]
    rest_endpoints = [RestEndpoint('https://api.hyperliquid.xyz', routes=Routes('/info'))]

    websocket_channels = {
        L2_BOOK: 'l2Book',
        TRADES: 'trades',
        L1_BOOK: 'bbo',
    }
    request_limit = 20
    valid_depths = [20]
    book_depth = 20

    @classmethod
    def timestamp_normalize(cls, ts: int) -> float:
        return ts / 1000.0

    @classmethod
    async def _fetch_symbol_data(cls, conn) -> list:
        address = cls.rest_endpoints[0].route('instruments')
        header = {'Content-Type': 'application/json'}
        perps = await conn.write(address, json.dumps({'type': 'meta'}), header=header)
        spot = await conn.write(address, json.dumps({'type': 'spotMeta'}), header=header)
        return [json.loads(perps, parse_float=Decimal), json.loads(spot, parse_float=Decimal)]

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        perps, spot = data

        for entry in perps['universe']:
            if entry.get('isDelisted'):
                continue
            symbol = Symbol(entry['name'], 'USD', type=PERPETUAL)
            info['instrument_type'][symbol.normalized] = PERPETUAL
            ret[symbol.normalized] = entry['name']

        tokens = spot.get('tokens', [])
        for entry in spot.get('universe', []):
            try:
                base, quote = (tokens[index]['name'] for index in entry['tokens'])
            except (IndexError, KeyError, ValueError):
                LOG.warning('%s: skipping spot pair %s, token indices %s do not resolve', cls.id, entry.get('name'), entry.get('tokens'))
                continue
            symbol = Symbol(base, quote, type=SPOT)
            info['instrument_type'][symbol.normalized] = SPOT
            ret[symbol.normalized] = entry['name']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.max_depth and self.max_depth > self.book_depth:
            raise ValueError(f'{self.id} serves a book exactly {self.book_depth} levels deep and offers no way to request more; {self.max_depth} was asked for')
        self._reset()

    def _reset(self):
        self._l2_book = {}

    async def subscribe(self, conn: AsyncConnection):
        self._reset()
        for channel, symbols in conn.subscription.items():
            for symbol in symbols:
                await conn.write(json.dumps({
                    'method': 'subscribe',
                    'subscription': {'type': channel, 'coin': symbol}
                }))

    async def _trades(self, msg: dict, timestamp: float):
        for entry in msg['data']:
            trade = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(entry['coin']),
                BUY if entry['side'] == 'B' else SELL,
                Decimal(entry['sz']),
                Decimal(entry['px']),
                self.timestamp_normalize(entry['time']),
                id=str(entry['tid']),
                raw=entry
            )
            await self.callback(TRADES, trade, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        data = msg['data']
        symbol = self.exchange_symbol_to_std_symbol(data['coin'])
        bids, asks = data['levels']

        if symbol not in self._l2_book:
            self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)
        self._l2_book[symbol].book.bids = {Decimal(level['px']): Decimal(level['sz']) for level in bids}
        self._l2_book[symbol].book.asks = {Decimal(level['px']): Decimal(level['sz']) for level in asks}

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, raw=msg, timestamp=self.timestamp_normalize(data['time']))

    async def _l1_book(self, msg: dict, timestamp: float):
        """
        {'channel': 'bbo', 'data': {'coin': 'BTC', 'time': 1787230121071,
         'bbo': [{'px': '71572.0', 'sz': '24.68755', 'n': 75}, {'px': '71573.0', ...}]}}
        """
        data = msg['data']
        bid, ask = data['bbo']
        if bid is None or ask is None:
            return
        book = L1Book(
            self.id,
            self.exchange_symbol_to_std_symbol(data['coin']),
            Decimal(bid['px']),
            Decimal(bid['sz']),
            Decimal(ask['px']),
            Decimal(ask['sz']),
            self.timestamp_normalize(data['time']),
            raw=msg
        )
        await self.callback(L1_BOOK, book, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        channel = msg.get('channel')

        if channel == 'trades':
            await self._trades(msg, timestamp)
        elif channel == 'l2Book':
            await self._book(msg, timestamp)
        elif channel == 'bbo':
            await self._l1_book(msg, timestamp)
        elif channel == 'subscriptionResponse':
            LOG.debug('%s: subscription confirmed: %s', self.id, msg.get('data'))
        elif channel == 'error':
            LOG.error('%s: venue reported an error: %s', self.id, msg.get('data'))
        elif channel == 'pong':
            pass
        else:
            LOG.warning('%s: unexpected message %s', self.id, msg)

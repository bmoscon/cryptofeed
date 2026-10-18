'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, List, Tuple, Union
import itertools

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, GEMINI, L2_BOOK, PERPETUAL, SELL, SPOT, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade


LOG = logging.getLogger(__name__)


class Gemini(Feed):
    id = GEMINI
    websocket_channels = {
        L2_BOOK: L2_BOOK,
        TRADES: TRADES
    }
    websocket_endpoints = [
        WebsocketEndpoint('wss://api.gemini.com/v2/marketdata/', sandbox='wss://api.sandbox.gemini.com/v2/marketdata/', channel_filter=[websocket_channels[L2_BOOK], websocket_channels[TRADES]])
    ]
    rest_endpoints = [RestEndpoint('https://api.gemini.com', routes=Routes('/v1/symbols/details/{}', currencies='/v1/symbols', l2book='/v1/book/{}?limit_bids={}&limit_asks={}'))]
    request_limit = 1

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.trade_watermark.key = lambda t: int(t.id)

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    async def _symbol_endpoint_prepare(cls, ep: RestEndpoint, conn) -> Union[List[str], str]:
        ret = json.loads(await conn.read(ep.route('currencies')), parse_float=Decimal)
        return [ep.route('instruments').format(currency) for currency in ret]

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for symbol in data:
            if symbol['status'] == 'closed':
                continue
            s = Symbol(symbol['base_currency'], symbol['quote_currency'], type=PERPETUAL if symbol['product_type'] == 'swap' else SPOT)
            ret[s.normalized] = symbol['symbol']
            info['tick_size'][s.normalized] = symbol['tick_size']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __reset(self, pairs):
        for pair in pairs:
            self._l2_book[self.exchange_symbol_to_std_symbol(pair)] = OrderBook(self.id, self.exchange_symbol_to_std_symbol(pair), max_depth=self.max_depth)

    async def _book(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        # Gemini sends ALL data for the symbol, so if we don't actually want
        # the book data, bail before parsing
        if self.subscription and ((L2_BOOK in self.subscription and msg['symbol'] not in self.subscription[L2_BOOK]) or L2_BOOK not in self.subscription):
            return

        data = msg['changes']
        forced = not len(self._l2_book[pair].book.bids)
        delta = {BID: [], ASK: []}
        for entry in data:
            side = ASK if entry[0] == 'sell' else BID
            price = Decimal(entry[1])
            amount = Decimal(entry[2])
            if amount == 0:
                if price in self._l2_book[pair].book[side]:
                    del self._l2_book[pair].book[side][price]
                    delta[side].append((price, 0))
            else:
                self._l2_book[pair].book[side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, delta=delta if not forced else None, raw=msg)

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        response = json.loads(data, parse_float=Decimal)
        bids = {Decimal(level['price']): Decimal(level['amount']) for level in response['bids']}
        asks = {Decimal(level['price']): Decimal(level['amount']) for level in response['asks']}
        book = OrderBook(self.id, symbol, max_depth=self.max_depth, bids=bids, asks=asks)
        stamps = [float(level['timestamp']) for level in response['bids'] + response['asks'] if level.get('timestamp')]
        book.timestamp = max(stamps) if stamps else None
        book.raw = response
        return book

    def _trades_subscribed(self, symbol: str) -> bool:
        # The l2 subscription delivers trades for every subscribed symbol, including
        # symbols that were only requested for L2_BOOK
        return not self.subscription or symbol in self.subscription.get(TRADES, [])

    def _trade_row(self, row: dict) -> Trade:
        return Trade(
            self.id,
            self.exchange_symbol_to_std_symbol(row['symbol']),
            SELL if row['side'] == 'sell' else BUY,
            Decimal(row['quantity']),
            Decimal(row['price']),
            self.timestamp_normalize(row['timestamp']),
            id=str(row['tid']),
            raw=row
        )

    async def _trade(self, msg: dict, timestamp: float):
        '''
        {"event_id": 1764553222813043, "price": "79722.23", "quantity": "0.0000621", "side": "buy", "symbol": "BTCUSD",
         "tid": 2840141021512809, "timestamp": 1787582029430, "type": "trade"}

        tid identifies the fill
        '''
        if not self._trades_subscribed(msg['symbol']):
            return
        for t in self.trade_watermark.live([self._trade_row(msg)]):
            await self.callback(TRADES, t, timestamp)

    async def _trade_batch(self, msg: dict, timestamp: float):
        if not self._trades_subscribed(msg['symbol']):
            return
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        for t in self.trade_watermark.batch([self._trade_row(row) for row in msg['trades']], symbol=symbol):
            await self.callback(TRADES, t, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'type' not in msg:
            LOG.warning('%s: Error from exchange %s', self.id, msg)
        elif msg['type'] == 'l2_updates':
            if 'trades' in msg:
                await self._trade_batch(msg, timestamp)
            await self._book(msg, timestamp)
        elif msg['type'] == 'trade':
            await self._trade(msg, timestamp)
        elif msg['type'] == 'heartbeat':
            return
        elif msg['type'] == 'auction_result' or msg['type'] == 'auction_indicative' or msg['type'] == 'auction_open':
            return
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        symbols = list(set(itertools.chain(*conn.subscription.values())))
        self.__reset(symbols)
        await conn.write(json.dumps({"type": "subscribe", "subscriptions": [{"name": "l2", "symbols": symbols}]}))

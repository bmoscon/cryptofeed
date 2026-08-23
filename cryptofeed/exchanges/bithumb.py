'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple
import uuid

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BITHUMB, BUY, L1_BOOK, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import L1Book, OrderBook, Ticker, Trade


LOG = logging.getLogger(__name__)


class Bithumb(Feed):
    id = BITHUMB
    book_delivery = 'snapshot'
    websocket_endpoints = [WebsocketEndpoint('wss://ws-api.bithumb.com/websocket/v1')]
    rest_endpoints = [RestEndpoint('https://api.bithumb.com', routes=Routes('/v1/market/all'))]
    websocket_channels = {
        L2_BOOK: 'orderbook',
        TRADES: 'trade',
        TICKER: 'ticker',
        L1_BOOK: 'l1_book',
    }

    @classmethod
    def timestamp_normalize(cls, ts: int) -> float:
        # for trades
        return ts / 1000

    @classmethod
    def _book_timestamp(cls, ts: int) -> float:
        # for orderbooks
        return ts / 1_000_000

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}

        for entry in data:
            quote, base = entry['market'].split('-')
            s = Symbol(base, quote)
            ret[s.normalized] = entry['market']
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    async def _trade(self, msg: dict, timestamp: float):
        '''
        {
            "type": "trade",
            "code": "KRW-BTC",
            "trade_price": 91195000,
            "trade_volume": 0.0005469,
            "ask_bid": "BID",
            "prev_closing_price": 91611000,
            "change": "FALL",
            "change_price": 416000,
            "trade_date": "2026-08-10",
            "trade_time": "23:25:54",
            "trade_timestamp": 1786371954790,
            "sequential_id": 953736236403549546,
            "timestamp": 1786371955039,
            "stream_type": "SNAPSHOT"
        }
        '''
        t = Trade(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['code']),
            BUY if msg['ask_bid'] == 'BID' else SELL,
            Decimal(msg['trade_volume']),
            Decimal(msg['trade_price']),
            self.timestamp_normalize(msg['trade_timestamp']),
            id=str(msg['sequential_id']),
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    @staticmethod
    def _book_sides(msg: dict) -> Tuple[Dict, Dict]:
        '''
        {
            "type": "orderbook",
            "code": "KRW-BTC",
            "total_ask_size": 4.5131,
            "total_bid_size": 0.1863,
            "orderbook_units": [{"ask_price": 91220000, "bid_price": 91200000, "ask_size": 0.1176, "bid_size": 0.0069},
                                ... 15 of them, best first ...],
            "level": 1,
            "timestamp": 1786371955004253,
            "stream_type": "REALTIME"
        }
        '''
        units = msg['orderbook_units']
        return ({Decimal(u['bid_price']): Decimal(u['bid_size']) for u in units if u['bid_price'] > 0 and u['bid_size'] > 0},
                {Decimal(u['ask_price']): Decimal(u['ask_size']) for u in units if u['ask_price'] > 0 and u['ask_size'] > 0})

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}

    async def _book(self, msg: dict, bids: Dict, asks: Dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['code'])
        if pair not in self._l2_book:
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)

        self._l2_book[pair].book.bids = bids
        self._l2_book[pair].book.asks = asks

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self._book_timestamp(msg['timestamp']), raw=msg)

    async def _ticker(self, msg: dict, bids: Dict, asks: Dict, timestamp: float):
        if not bids or not asks:
            return

        t = Ticker(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['code']),
            max(bids),
            min(asks),
            self._book_timestamp(msg['timestamp']),
            raw=msg
        )
        await self.callback(TICKER, t, timestamp)

    async def _l1_book(self, msg: dict, bids: Dict, asks: Dict, timestamp: float):
        if not bids or not asks:
            return

        bid = max(bids)
        ask = min(asks)
        book = L1Book(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['code']),
            bid,
            bids[bid],
            ask,
            asks[ask],
            self._book_timestamp(msg['timestamp']),
            raw=msg
        )
        await self.callback(L1_BOOK, book, timestamp)

    async def message_handler(self, msg: bytes, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'error' in msg:
            LOG.error("%s: error from exchange: %s", conn.uuid, msg['error'])
            return

        msg_type = msg.get('type')
        if msg_type == 'trade':
            await self._trade(msg, timestamp)
        elif msg_type == 'orderbook':
            bids, asks = self._book_sides(msg)
            if self.websocket_channels[L2_BOOK] in conn.subscription:
                await self._book(msg, bids, asks, timestamp)
            if self.websocket_channels[TICKER] in conn.subscription:
                await self._ticker(msg, bids, asks, timestamp)
            if self.websocket_channels[L1_BOOK] in conn.subscription:
                await self._l1_book(msg, bids, asks, timestamp)
        elif 'status' in msg:
            return
        else:
            LOG.warning("%s: Unhandled message %s", conn.uuid, msg)

    async def subscribe(self, conn: AsyncConnection):
        '''
        [{"ticket": "..."},
         {"type": "trade", "codes": ["KRW-BTC"]},
         {"type": "orderbook", "codes": ["KRW-BTC", "KRW-ETH"]}]
        '''
        self.__reset()
        chans = [{'ticket': str(uuid.uuid4())}]

        trades = conn.subscription.get(self.websocket_channels[TRADES], [])
        if trades:
            chans.append({'type': 'trade', 'codes': sorted(trades)})

        book = set(conn.subscription.get(self.websocket_channels[L2_BOOK], []))
        book |= set(conn.subscription.get(self.websocket_channels[TICKER], []))
        book |= set(conn.subscription.get(self.websocket_channels[L1_BOOK], []))
        if book:
            chans.append({'type': 'orderbook', 'codes': sorted(book)})

        await conn.write(json.dumps(chans))

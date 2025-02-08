'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from collections import defaultdict
import logging
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, CANDLES, KRAKEN, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.kraken_rest import KrakenRestMixin
from cryptofeed.types import OrderBook, Trade, Ticker, Candle


LOG = logging.getLogger('feedhandler')


class Kraken(Feed, KrakenRestMixin):
    id = KRAKEN
    websocket_endpoints = [WebsocketEndpoint('wss://ws.kraken.com', limit=20)]
    rest_endpoints = [RestEndpoint('https://api.kraken.com', routes=Routes('/0/public/AssetPairs'))]

    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '15d'}
    candle_interval_map = {'1m': 1, '5m': 5, '15m': 15, '30m': 30, '1h': 60, '4h': 240, '1d': 1440, '1w': 10080, '15d': 21600}
    valid_depths = [10, 25, 100, 500, 1000]
    websocket_channels = {
        L2_BOOK: 'book',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'ohlc'
    }
    request_limit = 10

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for symbol in data['result']:
            if 'wsname' not in data['result'][symbol] or '.d' in symbol:
                # https://blog.kraken.com/post/259/introducing-the-kraken-dark-pool/
                # .d is for dark pool symbols
                continue

            sym = data['result'][symbol]['wsname']
            sym = sym.replace('XBT', 'BTC').replace('XDG', 'DOGE')
            base, quote = sym.split("/")
            s = Symbol(base, quote)

            ret[s.normalized] = data['result'][symbol]['wsname']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, max_depth=1000, **kwargs):
        super().__init__(max_depth=max_depth, **kwargs)

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

    async def subscribe(self, conn: AsyncConnection):
        self.__reset(conn)
        for chan, symbols in conn.subscription.items():
            sub = {"name": chan}
            if self.exchange_channel_to_std(chan) == L2_BOOK:
                max_depth = self.max_depth if self.max_depth else 1000
                if max_depth not in self.valid_depths:
                    for d in self.valid_depths:
                        if d > max_depth:
                            max_depth = d
                            break

                sub['depth'] = max_depth
            if self.exchange_channel_to_std(chan) == CANDLES:
                sub['interval'] = self.candle_interval_map[self.candle_interval]

            await conn.write(json.dumps({
                "event": "subscribe",
                "pair": symbols,
                "subscription": sub
            }))

    async def _trade(self, msg: dict, pair: str, timestamp: float):
        """
        example message:

        [1,[["3417.20000","0.21222200","1549223326.971661","b","l",""]]]
        channel id, price, amount, timestamp, size, limit/market order, misc
        """
        for trade in msg[1]:
            price, amount, server_timestamp, side, order_type, _ = trade
            order_type = 'limit' if order_type == 'l' else 'market'
            t = Trade(
                self.id,
                pair,
                BUY if side == 'b' else SELL,
                Decimal(amount),
                Decimal(price),
                float(server_timestamp),
                type=order_type,
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _ticker(self, msg: dict, pair: str, timestamp: float):
        """
        [93, {'a': ['105.85000', 0, '0.46100000'], 'b': ['105.77000', 45, '45.00000000'], 'c': ['105.83000', '5.00000000'], 'v': ['92170.25739498', '121658.17399954'], 'p': ['107.58276', '107.95234'], 't': [4966, 6717], 'l': ['105.03000', '105.03000'], 'h': ['110.33000', '110.33000'], 'o': ['109.45000', '106.78000']}]
        channel id, asks: price, wholeLotVol, vol, bids: price, wholeLotVol, close: ...,, vol: ..., VWAP: ..., trades: ..., low: ...., high: ..., open: ...
        """
        t = Ticker(self.id, pair, Decimal(msg[1]['b'][0]), Decimal(msg[1]['a'][0]), None, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _book(self, msg: dict, pair: str, timestamp: float):
        delta = {BID: [], ASK: []}
        msg = msg[1:-2]

        if 'as' in msg[0]:
            # Snapshot
            bids = {Decimal(update[0]): Decimal(update[1]) for update in msg[0]['bs']}
            asks = {Decimal(update[0]): Decimal(update[1]) for update in msg[0]['as']}
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks, checksum_format='KRAKEN', truncate=self.max_depth != self.valid_depths[-1])
            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg)
        else:
            for m in msg:
                for s, updates in m.items():
                    side = False
                    if s == 'b':
                        side = BID
                    elif s == 'a':
                        side = ASK
                    if side:
                        for update in updates:
                            price, size, *_ = update
                            price = Decimal(price)
                            size = Decimal(size)
                            if size == 0:
                                # Per Kraken's technical support
                                # they deliver erroneous deletion messages
                                # periodically which should be ignored
                                if price in self._l2_book[pair].book[side]:
                                    del self._l2_book[pair].book[side][price]
                                    delta[side].append((price, 0))
                            else:
                                delta[side].append((price, size))
                                self._l2_book[pair].book[side][price] = size

            if self.checksum_validation and 'c' in msg[0] and self._l2_book[pair].book.checksum() != int(msg[0]['c']):
                raise BadChecksum("Checksum validation on orderbook failed")
            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, delta=delta, raw=msg, checksum=int(msg[0]['c']) if 'c' in msg[0] else None)

    async def _candle(self, msg: list, pair: str, timestamp: float):
        """
        [327,
            ['1621988141.603324',   start
             '1621988160.000000',   end
             '38220.70000',         open
             '38348.80000',         high
             '38220.70000',         low
             '38320.40000',         close
             '38330.59222',         vwap
             '3.23539643',          volume
             42                     count
            ],
        'ohlc-1',
        'XBT/USD']
        """
        start, end, open, high, low, close, _, volume, count = msg[1]
        interval = int(msg[-2].split("-")[-1])
        c = Candle(
            self.id,
            pair,
            float(end) - (interval * 60),
            float(end),
            self.normalize_candle_interval[interval],
            count,
            Decimal(open),
            Decimal(close),
            Decimal(high),
            Decimal(low),
            Decimal(volume),
            None,
            float(start),
            raw=msg
        )
        await self.callback(CANDLES, c, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg, list):
            channel, pair = msg[-2:]
            pair = self.exchange_symbol_to_std_symbol(pair)
            if channel == 'trade':
                await self._trade(msg, pair, timestamp)
            elif channel == 'ticker':
                await self._ticker(msg, pair, timestamp)
            elif channel[:4] == 'book':
                await self._book(msg, pair, timestamp)
            elif channel[:4] == 'ohlc':
                await self._candle(msg, pair, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            if msg['event'] == 'heartbeat':
                return
            elif msg['event'] == 'systemStatus':
                return
            elif msg['event'] == 'subscriptionStatus' and msg['status'] == 'subscribed':
                return
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)

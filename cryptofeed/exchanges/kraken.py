'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from collections import defaultdict
import logging
from typing import Dict, Tuple

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, CANDLES, KRAKEN, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade, Ticker, Candle


LOG = logging.getLogger(__name__)


class Kraken(Feed):
    id = KRAKEN
    provides_checksum = True
    websocket_endpoints = [WebsocketEndpoint('wss://ws.kraken.com/v2', limit=20)]
    rest_endpoints = [RestEndpoint('https://api.kraken.com', routes=Routes('/0/public/AssetPairs', l2book='/0/public/Depth?pair={}&count={}'))]

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
    ws_assets = {'XBT': 'BTC', 'XDG': 'DOGE'}

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for symbol in data['result']:
            if 'wsname' not in data['result'][symbol] or '.d' in symbol:
                # https://blog.kraken.com/post/259/introducing-the-kraken-dark-pool/
                # .d is for dark pool symbols
                continue

            wsname = data['result'][symbol]['wsname']
            base, quote = wsname.split("/")
            native = f"{cls.ws_assets.get(base, base)}/{cls.ws_assets.get(quote, quote)}"
            s = Symbol(*native.split("/"))
            ret[s.normalized] = native
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, max_depth=1000, **kwargs):
        super().__init__(max_depth=max_depth, **kwargs)
        depth = self.max_depth if self.max_depth else self.valid_depths[-1]
        self.book_depth = next((d for d in self.valid_depths if d >= depth), self.valid_depths[-1])

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

    async def subscribe(self, conn: AsyncConnection):
        self.__reset(conn)
        for chan, symbols in conn.subscription.items():
            params = {"channel": chan, "symbol": symbols}
            if self.exchange_channel_to_std(chan) == L2_BOOK:
                params['depth'] = self.book_depth
            if self.exchange_channel_to_std(chan) == CANDLES:
                params['interval'] = self.candle_interval_map[self.candle_interval]

            await conn.write(json.dumps({
                "method": "subscribe",
                "params": params
            }))

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'channel': 'trade',
            'type': 'update',
            'data': [{'symbol': 'BTC/USD', 'side': 'buy', 'price': 64668.9, 'qty': 0.00122657,
                      'ord_type': 'limit', 'trade_id': 104950594,
                      'timestamp': '2026-08-10T14:23:11.053094Z'}]
        }
        """
        for trade in msg['data']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(trade['symbol']),
                BUY if trade['side'] == 'buy' else SELL,
                Decimal(trade['qty']),
                Decimal(trade['price']),
                self.timestamp_normalize(trade['timestamp']),
                id=str(trade['trade_id']),
                type=trade['ord_type'],
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            'channel': 'ticker',
            'type': 'snapshot',
            'data': [{'symbol': 'BTC/USD', 'bid': 64666.5, 'bid_qty': 0.89031045, 'ask': 64666.6,
                      'ask_qty': 0.1103866, 'last': 64666.6, 'volume': 873.99355531,
                      'vwap': 65009.9, 'low': 64445.5, 'high': 65425.5, 'change': -458.2,
                      'change_pct': -0.7, 'trades': 33180,
                      'timestamp': '2026-08-10T14:23:48.736756Z'}]
        }
        """
        for update in msg['data']:
            t = Ticker(
                self.id,
                self.exchange_symbol_to_std_symbol(update['symbol']),
                Decimal(update['bid']),
                Decimal(update['ask']),
                self.timestamp_normalize(update['timestamp']),
                raw=update
            )
            await self.callback(TICKER, t, timestamp)

    @staticmethod
    def _tail(levels, count: int) -> list:
        size = len(levels)
        return [levels.index(index)[0] for index in range(max(0, size - count), size)]

    async def _book(self, msg: dict, timestamp: float):
        """
        {
            'channel': 'book',
            'type': 'update',
            'data': [{'symbol': 'BTC/USD', 'bids': [{'price': 64656.9, 'qty': 0.8907046}],
                      'asks': [], 'checksum': 455491965,
                      'timestamp': '2026-08-10T14:23:21.239992Z'}]
        }
        """
        for update in msg['data']:
            pair = self.exchange_symbol_to_std_symbol(update['symbol'])
            delta = None

            if msg['type'] == 'snapshot':
                bids = {Decimal(level['price']): Decimal(level['qty']) for level in update['bids']}
                asks = {Decimal(level['price']): Decimal(level['qty']) for level in update['asks']}
                self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.book_depth, truncate=True, checksum_format='KRAKEN', bids=bids, asks=asks)
            else:
                if pair not in self._l2_book:
                    continue
                delta = {BID: [], ASK: []}
                book = self._l2_book[pair].book
                for side, key in ((BID, 'bids'), (ASK, 'asks')):
                    inserts = sum(1 for level in update[key] if Decimal(level['qty']) != 0)
                    evictable = self._tail(book[side], inserts) if inserts else []

                    for level in update[key]:
                        price = Decimal(level['price'])
                        size = Decimal(level['qty'])
                        if size == 0:
                            # Per Kraken's technical support
                            # they deliver erroneous deletion messages
                            # periodically which should be ignored
                            if price in book[side]:
                                del book[side][price]
                                delta[side].append((price, size))
                        else:
                            delta[side].append((price, size))
                            book[side][price] = size

                    # an add that is not in the book landed outside the depth window
                    applied = [(price, size) for price, size in delta[side]
                               if size == 0 or price in book[side]]
                    reported = {price for price, _ in applied}
                    # a level gone from the book that this update did not delete was displaced
                    applied.extend((price, Decimal(0)) for price in evictable
                                   if price not in book[side] and price not in reported)
                    delta[side] = applied

            checksum = update.get('checksum')
            if self.checksum_validation and checksum is not None:
                if self._l2_book[pair].book.checksum() != checksum:
                    raise BadChecksum(f'{self.id}: {pair} checksum validation failed')
            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(update['timestamp']) if update.get('timestamp') else None, raw=msg, delta=delta, checksum=checksum)

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        response = json.loads(data, parse_float=Decimal)
        if response.get('error'):
            raise ValueError(f"{self.id}: book snapshot for {symbol} returned {response['error']}")
        result = response['result']
        if len(result) != 1:
            raise ValueError(f'{self.id}: book snapshot for {symbol} returned {len(result)} books, expected 1')
        entry = next(iter(result.values()))

        bids = {Decimal(price): Decimal(volume) for price, volume, *_ in entry['bids']}
        asks = {Decimal(price): Decimal(volume) for price, volume, *_ in entry['asks']}
        book = OrderBook(self.id, symbol, max_depth=self.max_depth, checksum_format=self.id, bids=bids, asks=asks)
        stamps = [level[2] for level in entry['bids'] + entry['asks'] if len(level) > 2]
        book.timestamp = float(max(stamps)) if stamps else None
        book.raw = entry
        return book

    async def _candle(self, msg: dict, timestamp: float):
        """
        {
            'channel': 'ohlc',
            'type': 'update',
            'timestamp': '2026-08-10T14:24:03.339853662Z',
            'data': [{'symbol': 'BTC/USD', 'open': 64672.2, 'high': 64672.2, 'low': 64666.8,
                      'close': 64666.8, 'trades': 3, 'volume': 0.00143597, 'vwap': 64672.0,
                      'interval_begin': '2026-08-10T14:24:00.000000000Z', 'interval': 1,
                      'timestamp': '2026-08-10T14:25:00.000000Z'}]
        }
        """
        ts = self.timestamp_normalize(msg['timestamp'])
        for update in msg['data']:
            start = self.timestamp_normalize(update['interval_begin'])
            stop = start + update['interval'] * 60
            c = Candle(
                self.id,
                self.exchange_symbol_to_std_symbol(update['symbol']),
                start,
                stop,
                self.normalize_candle_interval[update['interval']],
                update['trades'],
                Decimal(update['open']),
                Decimal(update['close']),
                Decimal(update['high']),
                Decimal(update['low']),
                Decimal(update['volume']),
                stop <= ts,
                ts,
                raw=update
            )
            await self.callback(CANDLES, c, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        channel = msg.get('channel')
        if channel == 'book':
            await self._book(msg, timestamp)
        elif channel == 'trade':
            await self._trade(msg, timestamp)
        elif channel == 'ticker':
            await self._ticker(msg, timestamp)
        elif channel == 'ohlc':
            await self._candle(msg, timestamp)
        elif channel == 'heartbeat':
            return
        elif channel == 'status':
            LOG.debug("%s: connection status %s", conn.uuid, msg['data'])
        elif 'method' in msg:
            if msg.get('success'):
                LOG.debug("%s: subscribed to %s", conn.uuid, msg['result'])
            else:
                LOG.error("%s: %s failed: %s", conn.uuid, msg['method'], msg.get('error'))
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

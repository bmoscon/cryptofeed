'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
import time
from typing import Dict, Tuple

from cryptofeed import _json as json

from cryptofeed.defines import ASK, BID, BUY, CANDLES, KUCOIN, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.types import OrderBook, Trade, Ticker, Candle


LOG = logging.getLogger(__name__)


class KuCoin(Feed):
    id = KUCOIN
    provides_sequence_number = True
    validates_sequence_number = True
    websocket_endpoints = [WebsocketEndpoint('wss://x-push-spot.kucoin.com')]
    TRADE_TYPE = 'SPOT'
    rest_endpoints = [RestEndpoint('https://api.kucoin.com', routes=Routes('/api/v1/symbols', l2book='/api/v1/market/orderbook/level2_100?symbol={}'))]
    BOOK_DEPTH = 'increment@10ms'

    valid_candle_intervals = {'1m', '3m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '1w'}
    candle_interval_map = {'1m': '1min', '3m': '3min', '15m': '15min', '30m': '30min', '1h': '1hour', '2h': '2hour', '4h': '4hour', '6h': '6hour', '8h': '8hour', '12h': '12hour', '1d': '1day', '1w': '1week'}

    websocket_channels = {
        L2_BOOK: 'obu',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'kline'
    }

    MAX_TOPICS_PER_CONNECTION = 200
    SUBSCRIBE_BATCH = 50
    SUBSCRIBE_PAUSE = 0.4
    keepalive_interval = 9.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'tick_size': {}, 'instrument_type': {}}
        for symbol in data['data']:
            if not symbol['enableTrading']:
                continue
            s = Symbol(symbol['baseCurrency'], symbol['quoteCurrency'])
            info['tick_size'][s.normalized] = symbol['priceIncrement']
            ret[s.normalized] = symbol['symbol']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.__reset()

    async def _pre_connect(self):
        topics = sum(len(symbols) for symbols in self.subscription.values())
        if topics > self.MAX_TOPICS_PER_CONNECTION:
            raise ValueError(f'{self.id}: {topics} topics requested (one per symbol per channel) and the venue allows {self.MAX_TOPICS_PER_CONNECTION} per connection')

    def __reset(self):
        self._l2_book = {}
        self.seq_no = {}

    async def _candles(self, msg: dict, symbol: str, timestamp: float):
        """
        {"T": "kline.SPOT", "P": 1787348631950441105,
         "d": {"a": "37892.88775774", "s": "BTC-USDT", "C": 1787348640, "c": "78245.1", "S": false,
               "v": "0.48447824", "h": "78247.9", "i": "1min", "l": "78202.2", "O": 1787348580,
               "o": "78202.2"}}
        """
        data = msg['d']
        interval = self.normalize_candle_interval[data['i']]
        c = Candle(
            self.id,
            symbol,
            int(data['O']),
            int(data['C']) - 1,
            interval,
            None,
            Decimal(data['o']),
            Decimal(data['c']),
            Decimal(data['h']),
            Decimal(data['l']),
            Decimal(data['v']),
            bool(data['S']),
            msg['P'] / 1_000_000_000,
            raw=msg
        )
        await self.callback(CANDLES, c, timestamp)

    async def _ticker(self, msg: dict, symbol: str, timestamp: float):
        """
        {"T": "ticker.SPOT", "P": 1787348157834794005,
         "d": {"A": "0.8210617", "B": "0.00760914", "E": 35866825780, "M": 1787348157830000000,
               "S": "SELL", "a": "78280.6", "b": "78280.5", "l": "78285.6", "q": "0.000161",
               "s": "BTC-USDT"}}
        """
        data = msg['d']
        t = Ticker(self.id, symbol, Decimal(data['b']), Decimal(data['a']),
                   data['M'] / 1_000_000_000, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _trades(self, msg: dict, symbol: str, timestamp: float):
        """
        {"T": "trade.SPOT", "P": 1787348155899171700,
         "d": {"E": 24021490985222144, "M": 1787348155897000000, "S": "sell", "p": "78313.6",
               "q": "0.00001374", "s": "BTC-USDT", "ti": "24021490985222144"}}
        """
        data = msg['d']
        t = Trade(
            self.id,
            symbol,
            BUY if data['S'].lower() == 'buy' else SELL,
            Decimal(data['q']),
            Decimal(data['p']),
            data['M'] / 1_000_000_000,
            id=str(data['ti']),
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    def _snapshot_url(self, symbol: str) -> str:
        return self.rest_endpoints[0].route('l2book', self.sandbox).format(symbol)

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        data = json.loads(data, parse_float=Decimal)['data']
        bids = {Decimal(price): Decimal(amount) for price, amount in data['bids']}
        asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}
        book = OrderBook(self.id, symbol, max_depth=self.max_depth, bids=bids, asks=asks)
        book.sequence_number = int(data['sequence'])
        book.raw = data
        return book

    async def _process_l2_book(self, msg: dict, symbol: str, timestamp: float):
        """
        snapshot: {"T":"obu.SPOT","dp":"increment@10ms","t":"snapshot","P":<ns>,
                   "d":{"C":35866811940,"M":<ns>,"O":35866811940,"a":[[p,q],...],"b":[...],"s":sym}}
        delta:    {"T":"obu.SPOT","dp":"increment@10ms","t":"delta","P":<ns>,
                   "d":{"C":35866811943,"M":<ns>,"O":35866811941,"a":[],"b":[[p,q]],"s":sym}}
        """
        data = msg['d']

        if msg.get('t') == 'snapshot':
            book = OrderBook(self.id, symbol, max_depth=self.max_depth,
                             bids={Decimal(price): Decimal(size) for price, size in data.get('b', [])},
                             asks={Decimal(price): Decimal(size) for price, size in data.get('a', [])})
            self._l2_book[symbol] = book
            self.seq_no[symbol] = data['C']
            await self.book_callback(L2_BOOK, book, timestamp, raw=msg,
                                     timestamp=data['M'] / 1_000_000_000,
                                     sequence_number=data['C'])
            return

        if symbol not in self._l2_book:
            return

        last = self.seq_no[symbol]
        if data['C'] <= last:
            return
        if data['O'] != last + 1:
            raise MissingSequenceNumber(f'{self.id} missing sequence number for {symbol}')
        self.seq_no[symbol] = data['C']

        delta = {BID: [], ASK: []}
        for key, side in (('b', BID), ('a', ASK)):
            for price, size in data.get(key, []):
                price = Decimal(price)
                size = Decimal(size)
                if size == 0:
                    if price in self._l2_book[symbol].book[side]:
                        del self._l2_book[symbol].book[side][price]
                        delta[side].append((price, size))
                else:
                    self._l2_book[symbol].book[side][price] = size
                    delta[side].append((price, size))

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, delta=delta, raw=msg, timestamp=data['M'] / 1_000_000_000, sequence_number=data['C'])

    async def keepalive(self, conn: AsyncConnection):
        await conn.write(json.dumps({'id': str(int(time.time() * 1000)), 'type': 'ping'}))

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'result' in msg:
            if msg['result'] in (False, 'false'):
                LOG.warning('%s: subscription rejected: %s', self.id,
                            msg.get('reason') or msg.get('message') or msg)
            return
        if msg.get('type') in {'pong', 'ack'}:
            return
        if msg.get('message') == 'welcome':
            return
        if msg.get('type') == 'error':
            LOG.warning('%s: error from exchange %s', self.id, msg)
            return

        topic = msg.get('T')
        if topic is None:
            LOG.warning('%s: Unhandled message type %s', self.id, msg)
            return

        channel = self.exchange_channel_to_std(topic.split('.')[0])
        symbol = self.exchange_symbol_to_std_symbol(msg['d']['s'])

        if channel == TICKER:
            await self._ticker(msg, symbol, timestamp)
        elif channel == TRADES:
            await self._trades(msg, symbol, timestamp)
        elif channel == CANDLES:
            await self._candles(msg, symbol, timestamp)
        elif channel == L2_BOOK:
            await self._process_l2_book(msg, symbol, timestamp)
        else:
            LOG.warning('%s: Unhandled message type %s', self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        request_id = 0
        for chan, symbols in self.subscription.items():
            channel = self.exchange_channel_to_std(chan)
            for symbol in symbols:
                request_id += 1
                frame = {'id': str(request_id), 'action': 'subscribe', 'channel': chan, 'tradeType': self.TRADE_TYPE, 'symbol': symbol}
                if channel == L2_BOOK:
                    frame['depth'] = self.BOOK_DEPTH
                elif channel == CANDLES:
                    frame['interval'] = self.candle_interval_map[self.candle_interval]

                await conn.write(json.dumps(frame))
                if request_id % self.SUBSCRIBE_BATCH == 0:
                    await asyncio.sleep(self.SUBSCRIBE_PAUSE)

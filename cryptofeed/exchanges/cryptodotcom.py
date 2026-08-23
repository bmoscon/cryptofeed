'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from decimal import Decimal
from typing import Dict, Optional, Tuple
from collections import defaultdict

from cryptofeed import _json as json
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint

from cryptofeed.defines import BUY, CANDLES, CRYPTODOTCOM, FUNDING, FUTURES, INDEX, L2_BOOK, OPEN_INTEREST, PERPETUAL, SELL, SPOT, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol, str_to_symbol
from cryptofeed.util.time import timedelta_str_to_sec
from cryptofeed.types import Trade, Ticker, Candle, Funding, Index, OpenInterest, OrderBook


LOG = logging.getLogger(__name__)


class CryptoDotCom(Feed):
    id = CRYPTODOTCOM
    book_delivery = 'snapshot'
    provides_sequence_number = True
    websocket_endpoints = [WebsocketEndpoint('wss://stream.crypto.com/exchange/v1/market')]
    rest_endpoints = [RestEndpoint('https://api.crypto.com', routes=Routes('/exchange/v1/public/get-instruments'))]

    websocket_channels = {
        L2_BOOK: 'book',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'candlestick',
        FUNDING: 'funding',
        INDEX: 'index',
        OPEN_INTEREST: 'open_interest'
    }
    request_limit = 100
    candle_interval_map = {'1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '1h': '1h', '2h': '2h',
                           '4h': '4h', '6h': '6h', '12h': '12h', '1d': '1D', '1w': '7D', '2w': '14D', '1M': '1M'}
    valid_candle_intervals = set(candle_interval_map)
    valid_depths = [10, 50, 150]
    book_depth = 150
    instrument_types = {'CCY_PAIR': SPOT, 'PERPETUAL_SWAP': PERPETUAL, 'FUTURE': FUTURES}

    @classmethod
    def timestamp_normalize(cls, ts: int) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['result']['data']:
            if not entry['tradable']:
                continue

            stype = cls.instrument_types.get(entry['inst_type'])
            if stype is None:
                LOG.warning("%s: skipping %s, unknown instrument type %s", cls.id, entry['symbol'], entry['inst_type'])
                continue

            sym = Symbol(entry['base_ccy'], entry['quote_ccy'], type=stype, expiry_date=entry['expiry_timestamp_ms'] / 1000 if stype == FUTURES else None)
            info['instrument_type'][sym.normalized] = stype
            info['tick_size'][sym.normalized] = Decimal(entry['price_tick_size'])
            ret[sym.normalized] = entry['symbol']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.max_depth:
            if self.max_depth > self.valid_depths[-1]:
                raise ValueError(f'{self.id} serves a book at most {self.valid_depths[-1]} levels deep, {self.max_depth} requested')
            self.book_depth = next(d for d in self.valid_depths if d >= self.max_depth)
        self.__reset()

    def __reset(self):
        self._l2_book = {}
        self._candles = {}
        self._candle_newest = {}
        self._candle_published = {}
        self._mark_price = {}
        self._predicted_rate = {}
        self._index_subscribers = defaultdict(list)

    @staticmethod
    def _index_symbol(symbol: str) -> Optional[str]:
        root, _, suffix = symbol.partition('-')
        return f'{root}-INDEX' if suffix else None

    def _topic(self, chan: str, symbol: str) -> Optional[str]:
        std_chan = self.exchange_channel_to_std(chan)
        if std_chan == L2_BOOK:
            return f"{chan}.{symbol}.{self.book_depth}"
        if std_chan == CANDLES:
            return f"{chan}.{self.candle_interval_map[self.candle_interval]}.{symbol}"
        if std_chan == INDEX:
            index = self._index_symbol(symbol)
            return f'{chan}.{index}' if index else None
        if std_chan == FUNDING and str_to_symbol(self.exchange_symbol_to_std_symbol(symbol)).type != PERPETUAL:
            return None
        return f"{chan}.{symbol}"

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        # API docs recommend a sleep between connect and subscription to avoid rate limiting
        await asyncio.sleep(1)

        ticker = self.websocket_channels[TICKER]
        requests = defaultdict(list)
        for chan, symbols in conn.subscription.items():
            chan = ticker if chan == self.websocket_channels[OPEN_INTEREST] else chan
            requests[chan].extend(filter(None, (self._topic(chan, symbol) for symbol in symbols)))

            if self.exchange_channel_to_std(chan) == INDEX:
                for symbol in symbols:
                    index = self._index_symbol(symbol)
                    if index:
                        self._index_subscribers[index].append(self.exchange_symbol_to_std_symbol(symbol))

            if self.exchange_channel_to_std(chan) == FUNDING:
                for extra in ('mark', 'estimatedfunding'):
                    requests[extra].extend(f'{extra}.{symbol}' for symbol in symbols
                                           if str_to_symbol(self.exchange_symbol_to_std_symbol(symbol)).type == PERPETUAL)

        for topics in requests.values():
            if not topics:
                continue
            await conn.write(json.dumps({"method": "subscribe",
                                         "params": {
                                             "channels": list(dict.fromkeys(topics))
                                         }}))
            await asyncio.sleep(1)

    async def _trades(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTC_USDT',
            'subscription': 'trade.BTC_USDT',
            'channel': 'trade',
            'data': [
                {
                    'd': '1786371795577193105',
                    't': 1786371795577,
                    'p': '64725.67',
                    'q': '0.00010',
                    's': 'SELL',
                    'i': 'BTC_USDT',
                    'm': '4611686018688057717'
                }
            ]
        }
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        for entry in msg['data']:
            t = Trade(
                self.id,
                symbol,
                BUY if entry['s'] == 'BUY' else SELL,
                Decimal(entry['q']),
                Decimal(entry['p']),
                self.timestamp_normalize(entry['t']),
                id=entry['d'],
                raw=entry
            )
            await self.callback(TRADES, t, timestamp)

    async def _ticker(self, msg: dict, conn: AsyncConnection, timestamp: float):
        '''
        {
            'instrument_name': 'BTCUSD-PERP',
            'subscription': 'ticker.BTCUSD-PERP',
            'channel': 'ticker',
            'data': [
                {
                    'h': '65441.0',
                    'l': '64455.2',
                    'a': '64668.9',
                    'c': '-0.0074',
                    'b': '64668.1',
                    'bs': '0.2901',
                    'k': '64668.2',
                    'ks': '0.1472',
                    'i': 'BTCUSD-PERP',
                    'v': '3185.0198',
                    'vv': '206846021.47',
                    'oi': '6115.5643',
                    't': 1786371789379
                }
            ]
        }
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        wants_ticker = self.websocket_channels[TICKER] in conn.subscription
        # spot instruments report oi as 0, so only publish it where it means something
        wants_oi = self.websocket_channels[OPEN_INTEREST] in conn.subscription and str_to_symbol(symbol).type != SPOT

        for entry in msg['data']:
            ts = self.timestamp_normalize(entry['t'])
            if wants_ticker:
                # an instrument with one side of the book empty omits that side's price
                t = Ticker(self.id, symbol,
                           Decimal(entry['b']) if entry.get('b') else Decimal(0),
                           Decimal(entry['k']) if entry.get('k') else Decimal(0),
                           ts, raw=entry)
                await self.callback(TICKER, t, timestamp)
            if wants_oi:
                await self.callback(OPEN_INTEREST, OpenInterest(self.id, symbol, Decimal(entry['oi']), ts, raw=entry), timestamp)

    async def _funding(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTCUSD-PERP',
            'subscription': 'funding.BTCUSD-PERP',
            'channel': 'funding',
            'data': [{'v': '-0.000000091', 't': 1786371785000}]
        }
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        for entry in msg['data']:
            f = Funding(self.id, symbol,
                        self._mark_price.get(symbol),
                        Decimal(entry['v']),
                        None,
                        self.timestamp_normalize(entry['t']),
                        predicted_rate=self._predicted_rate.get(symbol),
                        raw=entry)
            await self.callback(FUNDING, f, timestamp)

    async def _mark(self, msg: dict, timestamp: float):
        '''
        {'instrument_name': 'BTCUSD-PERP', 'subscription': 'mark.BTCUSD-PERP', 'channel': 'mark',
         'data': [{'v': '63652.3', 't': 1786480897000}]}
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        for entry in msg['data']:
            self._mark_price[symbol] = Decimal(entry['v'])

    async def _estimated_funding(self, msg: dict, timestamp: float):
        '''
        {'instrument_name': 'BTCUSD-PERP', 'subscription': 'estimatedfunding.BTCUSD-PERP',
         'channel': 'estimatedfunding', 'data': [{'v': '-0.000006242', 't': 1786480859000}]}
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        for entry in msg['data']:
            self._predicted_rate[symbol] = Decimal(entry['v'])

    async def _index(self, msg: dict, timestamp: float):
        '''
        {'instrument_name': 'BTCUSD-INDEX', 'subscription': 'index.BTCUSD-INDEX', 'channel': 'index',
         'data': [{'v': '63654.45', 't': 1786480897000}]}
        '''
        subscribers = self._index_subscribers.get(msg['instrument_name'], [])
        for entry in msg['data']:
            ts = self.timestamp_normalize(entry['t'])
            for symbol in subscribers:
                await self.callback(INDEX, Index(self.id, symbol, Decimal(entry['v']), ts, raw=entry), timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTC_USDT',
            'subscription': 'candlestick.1m.BTC_USDT',
            'channel': 'candlestick',
            'interval': '1m',
            'data': [
                {
                    'o': '64732.34',
                    'h': '64738.49',
                    'l': '64724.37',
                    'c': '64724.37',
                    'v': '0.50014',
                    't': 1786371780000,
                    'ut': 1786371795577
                }
            ]
        }
        '''
        interval = self.normalize_candle_interval[msg['interval']]
        symbol = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        newest = max(self._candle_newest.get(symbol, 0), max(entry['t'] for entry in msg['data']) / 1000)
        self._candle_newest[symbol] = newest

        held = self._candles.pop(symbol, None)
        if held is not None and held['t'] / 1000 < newest:
            await self._publish_candle(symbol, interval, held, True, timestamp)

        for entry in sorted(msg['data'], key=lambda e: e['t']):
            start = entry['t'] / 1000
            closed = start < newest

            if not self.candle_closed_only:
                await self._publish_candle(symbol, interval, entry, closed, timestamp)
            elif closed:
                if start > self._candle_published.get(symbol, 0):
                    self._candle_published[symbol] = start
                    await self._publish_candle(symbol, interval, entry, True, timestamp)
            else:
                self._candles[symbol] = entry

    async def _publish_candle(self, symbol: str, interval: str, entry: dict, closed: bool, timestamp: float):
        start = entry['t'] / 1000
        c = Candle(self.id,
                   symbol,
                   start,
                   start + timedelta_str_to_sec(interval) - 1,
                   interval,
                   None,
                   Decimal(entry['o']),
                   Decimal(entry['c']),
                   Decimal(entry['h']),
                   Decimal(entry['l']),
                   Decimal(entry['v']),
                   closed,
                   self.timestamp_normalize(entry['ut']),
                   raw=entry)
        await self.callback(CANDLES, c, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        '''
        {
            'instrument_name': 'BTC_USDT',
            'subscription': 'book.BTC_USDT.150',
            'channel': 'book',
            'depth': 150,
            'data': [
                {
                    'asks': [['64725.68', '0.22354', '7'], ['64725.79', '0.03151', '1'], ...],
                    'bids': [['64725.67', '0.13269', '3'], ['64725.62', '0.02319', '1'], ...],
                    't': 1786371789375,
                    'tt': 1786371789371,
                    'u': 354254250622496,
                    'cs': 457275660
                }
            ]
        }
        '''
        symbol = self.exchange_symbol_to_std_symbol(msg['instrument_name'])
        for entry in msg['data']:
            if symbol not in self._l2_book:
                self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)

            self._l2_book[symbol].book.bids = {Decimal(price): Decimal(size) for price, size, _ in entry['bids']}
            self._l2_book[symbol].book.asks = {Decimal(price): Decimal(size) for price, size, _ in entry['asks']}

            await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, timestamp=self.timestamp_normalize(entry['t']), sequence_number=entry['u'], raw=entry)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg.get('method') == 'public/heartbeat':
            await conn.write(json.dumps({'id': msg['id'], 'method': 'public/respond-heartbeat'}))
            return

        if msg['code'] != 0:
            LOG.warning("%s: Error received from exchange %s", self.id, msg)
            return

        result = msg.get('result')
        if result is None:
            return

        channel = result['channel']
        if channel == 'trade':
            await self._trades(result, timestamp)
        elif channel == 'ticker':
            await self._ticker(result, conn, timestamp)
        elif channel == 'candlestick':
            await self._candle(result, timestamp)
        elif channel == 'book':
            await self._book(result, timestamp)
        elif channel == 'funding':
            await self._funding(result, timestamp)
        elif channel == 'mark':
            await self._mark(result, timestamp)
        elif channel == 'estimatedfunding':
            await self._estimated_funding(result, timestamp)
        elif channel == 'index':
            await self._index(result, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

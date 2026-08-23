'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, List, Tuple, Union
from collections import defaultdict

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BID, BITGET, BUY, CANDLES, FUNDING, FUTURES, INDEX, L1_BOOK, L2_BOOK, OPEN_INTEREST, PERPETUAL, SELL, SPOT, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import L1Book, Ticker, Trade, Candle, Funding, Index, OpenInterest, OrderBook
from cryptofeed.util.time import timedelta_str_to_sec


LOG = logging.getLogger(__name__)


class Bitget(Feed):
    id = BITGET
    keepalive_interval = 30.0

    async def keepalive(self, conn: AsyncConnection):
        await conn.write('ping')
    provides_sequence_number = True
    validates_sequence_number = True
    websocket_endpoints = [WebsocketEndpoint('wss://ws.bitget.com/v2/ws/public')]
    rest_endpoints = [
        RestEndpoint('https://api.bitget.com', instrument_filter=('TYPE', (SPOT,)), routes=Routes('/api/v2/spot/public/symbols')),
        RestEndpoint('https://api.bitget.com', instrument_filter=('TYPE', (PERPETUAL, FUTURES)), routes=Routes(['/api/v2/mix/market/contracts?productType=USDT-FUTURES', '/api/v2/mix/market/contracts?productType=COIN-FUTURES', '/api/v2/mix/market/contracts?productType=USDC-FUTURES'])),
    ]

    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '6h', '12h', '1d', '3d', '1w', '1M'}
    candle_interval_map = {'1m': '1m', '5m': '5m', '15m': '15m', '30m': '30m', '1h': '1H', '4h': '4H', '6h': '6H', '12h': '12H', '1d': '1D', '3d': '3D', '1w': '1W', '1M': '1M'}
    websocket_channels = {
        L2_BOOK: 'books',
        L1_BOOK: 'books1',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'candle',
        FUNDING: 'ticker',
        INDEX: 'ticker',
        OPEN_INTEREST: 'ticker',
    }
    request_limit = 20

    @classmethod
    def timestamp_normalize(cls, ts: Union[int, str]) -> float:
        return int(ts) / 1000

    @classmethod
    def _product_types(cls, count: int) -> List:
        contracts = [route.split('productType=')[-1] for route in cls.rest_endpoints[1].routes.instruments]
        types = [None] + contracts
        if len(types) != count:
            raise ValueError(f'{cls.id}: {count} symbol responses for {len(types)} endpoints - the route list and _product_types disagree')
        return types

    @classmethod
    def _parse_symbol_data(cls, data: Union[List, Dict]) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        if isinstance(data, dict):
            data = [data]
        product_types = cls._product_types(len(data))
        for response, product_type in zip(data, product_types):
            for entry in response['data']:
                if 'symbolType' not in entry:
                    '''
                    spot

                    {
                        "symbol": "BTCUSDT",
                        "baseCoin": "BTC",
                        "quoteCoin": "USDT",
                        "pricePrecision": "2",
                        "quantityPrecision": "6",
                        "status": "online",
                        ...
                    }
                    '''
                    if entry['status'] != 'online':
                        continue
                    inst_type = 'SPOT'
                    sym = Symbol(entry['baseCoin'], entry['quoteCoin'])
                else:
                    '''
                    futures

                    {
                        "symbol": "BTCUSDT",
                        "baseCoin": "BTC",
                        "quoteCoin": "USDT",
                        "symbolType": "perpetual",
                        "symbolStatus": "normal",
                        "deliveryTime": "",
                        ...
                    }
                    '''
                    if entry['symbolStatus'] != 'normal':
                        continue
                    inst_type = product_type
                    if entry['symbolType'] == 'delivery':
                        sym = Symbol(entry['baseCoin'], entry['quoteCoin'], type=FUTURES, expiry_date=int(entry['deliveryTime']) / 1000)
                    else:
                        sym = Symbol(entry['baseCoin'], entry['quoteCoin'], type=PERPETUAL)

                ret[sym.normalized] = f"{entry['symbol']}_{inst_type}"
                info['instrument_type'][sym.normalized] = sym.type
                info['is_quanto'][sym.normalized] = inst_type == 'COIN-FUTURES'

        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.seq_no = {}

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]
                self.seq_no.pop(std_pair, None)

    async def _ticker(self, msg: dict, timestamp: float, symbol: str):
        '''
        spot

        {
            'action': 'snapshot',
            'arg': {'instType': 'SPOT', 'channel': 'ticker', 'instId': 'BTCUSDT'},
            'data': [
                {
                    'instId': 'BTCUSDT',
                    'lastPr': '64732.73',
                    'open24h': '65232.78',
                    'high24h': '65487.59',
                    'low24h': '64522',
                    'change24h': '-0.00680',
                    'bidPr': '64732.73',
                    'askPr': '64732.74',
                    'bidSz': '0.240886',
                    'askSz': '1.141205',
                    'baseVolume': '1029.893449',
                    'quoteVolume': '67018089.479221',
                    'openUtc': '64898.06',
                    'changeUtc24h': '-0.00255',
                    'ts': '1786371836986'
                }
            ],
            'ts': 1786371836990
        }

        derivatives send the same fields plus fundingRate, nextFundingTime, markPrice, indexPrice and
        holdingAmount (open interest), which is why funding, index and open interest ride this channel
        '''
        for entry in msg['data']:
            ts = self.timestamp_normalize(entry['ts'])

            if entry['bidPr'] and entry['askPr']:
                t = Ticker(
                    self.id,
                    symbol,
                    Decimal(entry['bidPr']),
                    Decimal(entry['askPr']),
                    ts,
                    raw=entry
                )
                await self.callback(TICKER, t, timestamp)

            if entry.get('indexPrice'):
                i = Index(
                    self.id,
                    symbol,
                    Decimal(entry['indexPrice']),
                    ts,
                    raw=entry
                )
                await self.callback(INDEX, i, timestamp)

            if entry.get('holdingAmount'):
                o = OpenInterest(
                    self.id,
                    symbol,
                    Decimal(entry['holdingAmount']),
                    ts,
                    raw=entry
                )
                await self.callback(OPEN_INTEREST, o, timestamp)

            # delivery contracts report a zeroed funding rate and no next funding time
            next_funding = entry.get('nextFundingTime')
            if next_funding and next_funding != '0':
                f = Funding(
                    self.id,
                    symbol,
                    Decimal(entry['markPrice']),
                    Decimal(entry['fundingRate']),
                    self.timestamp_normalize(next_funding),
                    ts,
                    raw=entry
                )
                await self.callback(FUNDING, f, timestamp)

    async def _trade(self, msg: dict, timestamp: float, symbol: str):
        '''
        {
            'action': 'update',
            'arg': {'instType': 'SPOT', 'channel': 'trade', 'instId': 'BTCUSDT'},
            'data': [
                {
                    'ts': '1786371841905',
                    'price': '64732.74',
                    'size': '0.000016',
                    'side': 'buy',
                    'tradeId': '1470715589993152512'
                }
            ],
            'ts': 1786371841906
        }
        '''
        for entry in msg['data']:
            t = Trade(
                self.id,
                symbol,
                BUY if entry['side'] == 'buy' else SELL,
                Decimal(entry['size']),
                Decimal(entry['price']),
                self.timestamp_normalize(entry['ts']),
                id=entry['tradeId'],
                raw=entry
            )
            await self.callback(TRADES, t, timestamp)

    async def _candle(self, msg: dict, timestamp: float, symbol: str):
        '''
        {
            'action': 'update',
            'arg': {'instType': 'SPOT', 'channel': 'candle1m', 'instId': 'BTCUSDT'},
            'data': [['1786371840000', '64732.74', '64732.74', '64732.74', '64732.74', '0', '0', '0']],
            'ts': 1786371840606
        }

        start, open, high, low, close, base volume, quote volume, USDT volume
        '''
        interval = timedelta_str_to_sec(self.candle_interval)
        ts = self.timestamp_normalize(msg['ts'])

        for entry in msg['data']:
            start = self.timestamp_normalize(entry[0])
            # the exchange sends no 'confirm' flag, so closed is derived from the interval
            closed = start + interval <= ts
            if self.candle_closed_only and not closed:
                continue
            c = Candle(
                self.id,
                symbol,
                start,
                start + interval,
                self.candle_interval,
                None,
                Decimal(entry[1]),
                Decimal(entry[4]),
                Decimal(entry[2]),
                Decimal(entry[3]),
                Decimal(entry[5]),
                closed,
                ts,
                raw=entry
            )
            await self.callback(CANDLES, c, timestamp)

    async def _book(self, msg: dict, timestamp: float, symbol: str):
        '''
        {
            'action': 'update',
            'arg': {'instType': 'SPOT', 'channel': 'books', 'instId': 'BTCUSDT'},
            'data': [
                {
                    'asks': [['64745.76', '0.863769'], ['64746.69', '0.030926']],
                    'bids': [],
                    'ts': '1786371837600',
                    'seq': 702294710791,
                    'pseq': 702294703025
                }
            ],
            'ts': 1786371837602
        }
        '''
        data = msg['data'][0]
        delta = None

        if msg['action'] == 'snapshot':
            bids = {Decimal(price): Decimal(size) for price, size in data['bids']}
            asks = {Decimal(price): Decimal(size) for price, size in data['asks']}
            self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth, bids=bids, asks=asks)
        else:
            if symbol not in self._l2_book:
                return
            if data.get('pseq') is not None and self.seq_no.get(symbol) not in (None, data['pseq']):
                raise MissingSequenceNumber(f"{self.id}: {symbol} book expected sequence number {self.seq_no.get(symbol)}, got {data['pseq']}")
            book = self._l2_book[symbol].book
            delta = {BID: [], ASK: []}
            for side, key in ((BID, 'bids'), (ASK, 'asks')):
                for price, size in data[key]:
                    price = Decimal(price)
                    size = Decimal(size)
                    delta[side].append((price, size))

                    if size == 0:
                        if price in book[side]:
                            del book[side][price]
                    else:
                        book[side][price] = size

        self.seq_no[symbol] = data['seq']
        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, delta=delta, sequence_number=data['seq'], timestamp=self.timestamp_normalize(msg['ts']), raw=msg)

    async def _l1_book(self, msg: dict, timestamp: float, symbol: str):
        '''
        {
            'action': 'snapshot',
            'arg': {'instType': 'SPOT', 'channel': 'books1', 'instId': 'BTCUSDT'},
            'data': [{'asks': [['64745.76', '0.863769']], 'bids': [['64745.75', '0.1']],
                      'ts': '1786371837600', 'seq': 702294710791}],
            'ts': 1786371837602
        }
        '''
        data = msg['data'][0]
        if not data['bids'] or not data['asks']:
            return

        bid, bid_size = data['bids'][0]
        ask, ask_size = data['asks'][0]
        book = L1Book(self.id, symbol, Decimal(bid), Decimal(bid_size), Decimal(ask), Decimal(ask_size), self.timestamp_normalize(msg['ts']), raw=msg)
        await self.callback(L1_BOOK, book, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        if msg == 'pong':
            return
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            # {'event': 'subscribe', 'arg': {'instType': 'SPOT', 'channel': 'ticker', 'instId': 'BTCUSDT'}}
            if msg['event'] == 'error':
                LOG.error('%s: Error from exchange: %s', conn.uuid, msg)
            return

        channel = msg['arg']['channel']
        symbol = self.exchange_symbol_to_std_symbol(f"{msg['arg']['instId']}_{msg['arg']['instType']}")

        if channel == 'books':
            await self._book(msg, timestamp, symbol)
        elif channel == 'books1':
            await self._l1_book(msg, timestamp, symbol)
        elif channel == 'ticker':
            await self._ticker(msg, timestamp, symbol)
        elif channel == 'trade':
            await self._trade(msg, timestamp, symbol)
        elif channel.startswith('candle'):
            await self._candle(msg, timestamp, symbol)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset(conn)
        args = []

        for chan, symbols in conn.subscription.items():
            if chan == self.std_channel_to_exchange(CANDLES):
                chan += self.candle_interval_map[self.candle_interval]
            for s in symbols:
                inst_id, inst_type = s.split('_', 1)
                args.append({'instType': inst_type, 'channel': chan, 'instId': inst_id})

        await conn.write(json.dumps({"op": "subscribe", "args": args}))

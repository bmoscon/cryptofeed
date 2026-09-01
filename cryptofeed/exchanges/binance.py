'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from collections import defaultdict
from decimal import Decimal
import time
from typing import Dict, Union, Tuple

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, HTTPPoll, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BID, BINANCE, BUY, CANDLES, FUNDING, FUTURES, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, PERPETUAL, SELL, SPOT, TICKER, TRADES, FILLED, UNFILLED
from cryptofeed.exceptions import UnsupportedDataFeed, UnsupportedSymbol
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import Trade, Ticker, Candle, Liquidation, Funding, OpenInterest, OrderBook


LOG = logging.getLogger(__name__)


def _chunk(items: list, n: int):
    for i in range(0, len(items), n):
        yield items[i:i + n]


class BinanceBase(Feed):
    provides_sequence_number = True
    DEFAULT_SNAPSHOT_DEPTH = 1000
    SNAPSHOT_RETRIES = 5
    SNAPSHOT_RETRY_DELAY = 15
    # m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'}
    websocket_channels = {
        L2_BOOK: 'depth',
        TRADES: 'aggTrade',
        TICKER: 'bookTicker',
        CANDLES: 'kline_',
    }
    request_limit = 20
    per_connection_limit = 1024

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        for symbol in data['symbols']:
            if symbol.get('status', 'TRADING') != "TRADING":
                continue
            if symbol.get('contractStatus', 'TRADING') != "TRADING":
                continue

            expiration = None
            contract_type = symbol.get('contractType')
            if not contract_type:
                stype = SPOT
            elif contract_type in ('PERPETUAL', 'TRADIFI_PERPETUAL'):
                stype = PERPETUAL
            elif contract_type in ('CURRENT_QUARTER', 'NEXT_QUARTER'):
                stype = FUTURES
                expiration = symbol['symbol'].split("_")[1]
            else:
                cls.unsupported_category('contractType', contract_type)
                continue

            s = Symbol(symbol['baseAsset'], symbol['quoteAsset'], type=stype, expiry_date=expiration)
            ret[s.normalized] = symbol['symbol']
            info['tick_size'][s.normalized] = symbol['filters'][0]['tickSize']
            info['instrument_type'][s.normalized] = stype
        return ret, info

    def __init__(self, depth_interval='100ms', open_interest_interval=1.0, **kwargs):
        """
        depth_interval: str
            time between l2_book/delta updates {'100ms', '1000ms'} (different from BINANCE_FUTURES & BINANCE_DELIVERY)
        open_interest_interval: float
            time in seconds between open_interest polls
        """
        if depth_interval is not None and depth_interval not in self.valid_depth_intervals:
            raise ValueError(f"Depth interval must be one of {self.valid_depth_intervals}")

        super().__init__(**kwargs)
        self.depth_interval = depth_interval
        self.open_interest_interval = open_interest_interval
        self._open_interest_cache = {}
        self._reset()

    def _connect_rest(self):
        if 'open_interest' not in self.subscription:
            return []
        route = self.rest_endpoints[0].routes.open_interest
        if route is None:
            raise UnsupportedDataFeed(f'{self.id} no open interest endpoint to poll')

        addrs = [self.rest_endpoints[0].route('open_interest', sandbox=self.sandbox).format(pair) for pair in self.subscription['open_interest']]
        return [(HTTPPoll(addrs, self.id, delay=60.0, sleep=self.open_interest_interval, proxy=self.http_proxy), self.subscribe, self.message_handler)]

    async def _open_interest(self, msg: dict, timestamp: float):
        """
        {
            "openInterest": "10659.509",
            "symbol": "BTCUSDT",
            "time": 1589437530011   // Transaction time
        }
        """
        pair = msg['symbol']
        oi = msg['openInterest']
        if oi != self._open_interest_cache.get(pair, None):
            o = OpenInterest(
                self.id,
                self.exchange_symbol_to_std_symbol(pair),
                Decimal(oi),
                self.timestamp_normalize(msg['time']),
                raw=msg
            )
            await self.callback(OPEN_INTEREST, o, timestamp)
            self._open_interest_cache[pair] = oi

    def _address(self) -> Union[str, Dict]:
        """
        Binance has a 200 pair/stream limit per connection, so we need to break the address
        down into multiple connections if necessary. Because the key is currently not used
        for the address dict, we can just set it to the last used stream, since this will be
        unique.

        The generic connect method supplied by Feed will take care of creating the
        correct connection objects from the addresses.
        """
        address = self.address + '/stream?streams='
        subs = self._stream_names()

        if 0 < len(subs) < self.per_connection_limit:
            return address + '/'.join(subs)
        else:
            return [address + '/'.join(chunk) for chunk in _chunk(subs, self.per_connection_limit)]

    def _stream_names(self) -> list:
        subs = []
        for chan in self.subscription:
            normalized_chan = self.exchange_channel_to_std(chan)
            if normalized_chan == OPEN_INTEREST:
                continue

            stream = chan
            if normalized_chan == CANDLES:
                stream = f"{chan}{self.candle_interval}"
            elif normalized_chan == L2_BOOK:
                stream = f"{chan}@{self.depth_interval}"

            for pair in self.subscription[chan]:
                # for everything but premium index the symbols need to be lowercase.
                if pair.startswith("p"):
                    if normalized_chan != CANDLES:
                        raise ValueError("Premium Index Symbols only allowed on Candle data feed")
                else:
                    pair = pair.lower()
                subs.append(f"{pair}@{stream}")
        return subs

    def _reset(self, conn: AsyncConnection = None):
        if conn is None:
            self._l2_book = {}
            self.last_update_id = {}
            return

        for pair in self._connection_book_pairs(conn):
            self._drop_book(pair)

    def _connection_book_pairs(self, conn: AsyncConnection) -> list:
        address = getattr(conn, 'address', None) or ''
        if 'streams=' not in address:
            book_channel = self.websocket_channels[L2_BOOK]
            symbols = (getattr(conn, 'subscription', None) or {}).get(book_channel, [])
            return [self.exchange_symbol_to_std_symbol(symbol) for symbol in symbols]

        pairs = []
        for name in address.split('streams=', 1)[1].split('/'):
            symbol, _, stream = name.partition('@')
            if not stream.startswith(self.websocket_channels[L2_BOOK]):
                continue
            try:
                pairs.append(self.exchange_symbol_to_std_symbol(symbol.upper()))
            except UnsupportedSymbol:
                continue

        return pairs

    def _drop_book(self, std_pair: str):
        self._l2_book.pop(std_pair, None)
        self.last_update_id.pop(std_pair, None)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            "e": "aggTrade",  // Event type
            "E": 123456789,   // Event time
            "s": "BNBBTC",    // Symbol
            "a": 12345,       // Aggregate trade ID
            "p": "0.001",     // Price
            "q": "100",       // Quantity
            "f": 100,         // First trade ID
            "l": 105,         // Last trade ID
            "T": 123456785,   // Trade time
            "m": true,        // Is the buyer the market maker?
            "M": true         // Ignore
        }
        """
        t = Trade(self.id,
                  self.exchange_symbol_to_std_symbol(msg['s']),
                  SELL if msg['m'] else BUY,
                  Decimal(msg['q']),
                  Decimal(msg['p']),
                  self.timestamp_normalize(msg['T']),
                  id=str(msg['a']),
                  raw=msg)
        await self.callback(TRADES, t, timestamp)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            'u': 382569232,
            's': 'FETUSDT',
            'b': '0.36031000',
            'B': '1500.00000000',
            'a': '0.36092000',
            'A': '176.40000000'
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['s'])
        bid = Decimal(msg['b'])
        ask = Decimal(msg['a'])

        # Binance does not have a timestamp in this update, but the two futures APIs do
        if 'E' in msg:
            ts = self.timestamp_normalize(msg['E'])
        else:
            ts = timestamp

        t = Ticker(self.id, pair, bid, ask, ts, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _liquidations(self, msg: dict, timestamp: float):
        """
        {
        "e":"forceOrder",       // Event Type
        "E":1568014460893,      // Event Time
        "o":{
            "s":"BTCUSDT",      // Symbol
            "S":"SELL",         // Side
            "o":"LIMIT",        // Order Type
            "f":"IOC",          // Time in Force
            "q":"0.014",        // Original Quantity
            "p":"9910",         // Price
            "ap":"9910",        // Average Price
            "X":"FILLED",       // Order Status
            "l":"0.014",        // Order Last Filled Quantity
            "z":"0.014",        // Order Filled Accumulated Quantity
            "T":1568014460893,  // Order Trade Time
            }
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['o']['s'])
        liq = Liquidation(self.id,
                          pair,
                          SELL if msg['o']['S'] == 'SELL' else BUY,
                          Decimal(msg['o']['q']),
                          Decimal(msg['o']['p']),
                          None,
                          FILLED if msg['o']['X'] == 'FILLED' else UNFILLED,
                          self.timestamp_normalize(msg['E']),
                          raw=msg)
        await self.callback(LIQUIDATIONS, liq, receipt_timestamp=timestamp)

    def _check_update_id(self, std_pair: str, msg: dict) -> bool:
        """
        Messages will be queued while fetching snapshot and we can return a book_callback
        using this msg's data instead of waiting for the next update.
        """
        if self._l2_book[std_pair].delta is None and msg['u'] <= self.last_update_id[std_pair]:
            return True
        elif msg['U'] <= self.last_update_id[std_pair] and msg['u'] <= self.last_update_id[std_pair]:
            # Old message, can ignore it
            return True
        elif msg['U'] <= self.last_update_id[std_pair] + 1 <= msg['u']:
            self.last_update_id[std_pair] = msg['u']
            return False
        elif self.last_update_id[std_pair] + 1 == msg['U']:
            self.last_update_id[std_pair] = msg['u']
            return False
        else:
            self._drop_book(std_pair)
            LOG.warning("%s: %s missing book update detected, resetting book", self.id, std_pair)
            return True

    def _snapshot_depth(self) -> int:
        deepest = max(self.valid_depths)
        if not self.max_depth:
            return min(self.DEFAULT_SNAPSHOT_DEPTH, deepest)
        if self.max_depth >= deepest:
            return deepest
        for depth in self.valid_depths:
            if depth >= self.max_depth:
                return depth
        return deepest

    def _snapshot_url(self, symbol: str) -> str:
        return self.rest_endpoints[0].route('l2book', self.sandbox).format(symbol, self._snapshot_depth())

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        resp = json.loads(data, parse_float=Decimal)
        book = OrderBook(self.id, symbol, max_depth=self.max_depth, bids={Decimal(u[0]): Decimal(u[1]) for u in resp['bids']}, asks={Decimal(u[0]): Decimal(u[1]) for u in resp['asks']})
        book.timestamp = self.timestamp_normalize(resp['E']) if 'E' in resp else None
        book.sequence_number = resp['lastUpdateId']
        book.raw = resp
        return book

    async def _snapshot(self, pair: str) -> None:
        response = await self.http_conn.read(self._snapshot_url(pair), retry_count=self.SNAPSHOT_RETRIES, retry_delay=self.SNAPSHOT_RETRY_DELAY)
        std_pair = self.exchange_symbol_to_std_symbol(pair)
        book = self._parse_snapshot(std_pair, response)

        self.last_update_id[std_pair] = book.sequence_number
        self._l2_book[std_pair] = book
        await self.book_callback(L2_BOOK, book, time.time(), timestamp=book.timestamp, raw=book.raw, sequence_number=book.sequence_number)

    async def _book(self, msg: dict, pair: str, timestamp: float):
        """
        {
            "e": "depthUpdate", // Event type
            "E": 123456789,     // Event time
            "s": "BNBBTC",      // Symbol
            "U": 157,           // First update ID in event
            "u": 160,           // Final update ID in event
            "b": [              // Bids to be updated
                    [
                        "0.0024",       // Price level to be updated
                        "10"            // Quantity
                    ]
            ],
            "a": [              // Asks to be updated
                    [
                        "0.0026",       // Price level to be updated
                        "100"           // Quantity
                    ]
            ]
        }
        """
        exchange_pair = pair
        pair = self.exchange_symbol_to_std_symbol(pair)

        if pair not in self._l2_book:
            await self._snapshot(exchange_pair)

        skip_update = self._check_update_id(pair, msg)
        if skip_update:
            return

        delta = {BID: [], ASK: []}

        for s, side in (('b', BID), ('a', ASK)):
            for update in msg[s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])
                delta[side].append((price, amount))

                if amount == 0:
                    if price in self._l2_book[pair].book[side]:
                        del self._l2_book[pair].book[side][price]
                else:
                    self._l2_book[pair].book[side][price] = amount

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(msg['E']), raw=msg, delta=delta, sequence_number=self.last_update_id[pair])

    async def _funding(self, msg: dict, timestamp: float):
        """
        {
            "e": "markPriceUpdate",  // Event type
            "E": 1562305380000,      // Event time
            "s": "BTCUSDT",          // Symbol
            "p": "11185.87786614",   // Mark price
            "r": "0.00030000",       // Funding rate
            "T": 1562306400000       // Next funding time
        }

        BinanceFutures
        {
            "e": "markPriceUpdate",     // Event type
            "E": 1562305380000,         // Event time
            "s": "BTCUSDT",             // Symbol
            "p": "11185.87786614",      // Mark price
            "i": "11784.62659091"       // Index price
            "P": "11784.25641265",      // Estimated Settle Price, only useful in the last hour before the settlement starts
            "r": "0.00030000",          // Funding rate
            "T": 1562306400000          // Next funding time
        }
        """
        next_time = self.timestamp_normalize(msg['T']) if msg['T'] > 0 else None
        rate = Decimal(msg['r']) if msg['r'] else None
        if next_time is None:
            rate = None

        f = Funding(self.id,
                    self.exchange_symbol_to_std_symbol(msg['s']),
                    Decimal(msg['p']),
                    rate,
                    next_time,
                    self.timestamp_normalize(msg['E']),
                    predicted_rate=Decimal(msg['P']) if 'P' in msg and msg['P'] is not None else None,
                    raw=msg)
        await self.callback(FUNDING, f, timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        """
        {
            'e': 'kline',
            'E': 1615927655524,
            's': 'BTCUSDT',
            'k': {
                't': 1615927620000,
                'T': 1615927679999,
                's': 'BTCUSDT',
                'i': '1m',
                'f': 710917276,
                'L': 710917780,
                'o': '56215.99000000',
                'c': '56232.07000000',
                'h': '56238.59000000',
                'l': '56181.99000000',
                'v': '13.80522200',
                'n': 505,
                'x': False,
                'q': '775978.37383076',
                'V': '7.19660600',
                'Q': '404521.60814919',
                'B': '0'
            }
        }
        """
        if self.candle_closed_only and not msg['k']['x']:
            return
        c = Candle(self.id,
                   self.exchange_symbol_to_std_symbol(msg['s']),
                   msg['k']['t'] / 1000,
                   msg['k']['T'] / 1000,
                   msg['k']['i'],
                   msg['k']['n'],
                   Decimal(msg['k']['o']),
                   Decimal(msg['k']['c']),
                   Decimal(msg['k']['h']),
                   Decimal(msg['k']['l']),
                   Decimal(msg['k']['v']),
                   msg['k']['x'],
                   self.timestamp_normalize(msg['E']),
                   raw=msg)
        await self.callback(CANDLES, c, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'openInterest' in msg:
            return await self._open_interest(msg, timestamp)

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']
        pair = pair.upper()

        event = msg.get('e')
        if event == 'depthUpdate':
            await self._book(msg, pair, timestamp)
        elif event == 'aggTrade':
            await self._trade(msg, timestamp)
        elif event == 'forceOrder':
            await self._liquidations(msg, timestamp)
        elif event == 'markPriceUpdate':
            await self._funding(msg, timestamp)
        elif event == 'kline':
            await self._candle(msg, timestamp)
        elif event == 'bookTicker' or (event is None and 'A' in msg):
            await self._ticker(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        # Binance does not have a separate subscribe message, the
        # subscription information is included in the
        # connection endpoint
        if not isinstance(conn, HTTPPoll):
            self._reset(conn)


class Binance(BinanceBase):
    id = BINANCE
    DEFAULT_SNAPSHOT_DEPTH = 5000
    websocket_endpoints = [WebsocketEndpoint('wss://stream.binance.com:9443', sandbox='wss://testnet.binance.vision')]
    rest_endpoints = [RestEndpoint('https://api.binance.com', routes=Routes('/api/v3/exchangeInfo', l2book='/api/v3/depth?symbol={}&limit={}'), sandbox='https://testnet.binance.vision')]

    valid_depths = [5, 10, 20, 50, 100, 500, 1000, 5000]
    valid_depth_intervals = {'100ms', '1000ms'}

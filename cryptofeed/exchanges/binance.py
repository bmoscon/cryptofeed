'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from asyncio import create_task
from collections import defaultdict, deque
from decimal import Decimal
from typing import Dict, Union, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll, HTTPConcurrentPoll
from cryptofeed.defines import BID, ASK, BINANCE, BUY, CANDLES, FUNDING, FUTURES, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, PERPETUAL, SELL, SPOT, TICKER, TRADES, FILLED, UNFILLED
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.binance_rest import BinanceRestMixin
from cryptofeed.types import Trade, Ticker, Candle, Liquidation, Funding, OrderBook


LOG = logging.getLogger('feedhandler')


class Binance(Feed, BinanceRestMixin):
    id = BINANCE
    symbol_endpoint = 'https://api.binance.com/api/v3/exchangeInfo'
    valid_depths = [5, 10, 20, 50, 100, 500, 1000, 5000]
    # m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'}
    valid_depth_intervals = {'100ms', '1000ms'}
    websocket_channels = {
        L2_BOOK: 'depth',
        TRADES: 'aggTrade',
        TICKER: 'bookTicker',
        CANDLES: 'kline_'
    }
    request_limit = 20

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
            stype = SPOT
            if symbol.get('contractType') == 'PERPETUAL':
                stype = PERPETUAL
            elif symbol.get('contractType') in ('CURRENT_QUARTER', 'NEXT_QUARTER'):
                stype = FUTURES
                expiration = symbol['symbol'].split("_")[1]

            s = Symbol(symbol['baseAsset'], symbol['quoteAsset'], type=stype, expiry_date=expiration)
            ret[s.normalized] = symbol['symbol']
            info['tick_size'][s.normalized] = symbol['filters'][0]['tickSize']
            info['instrument_type'][s.normalized] = stype
        return ret, info

    def __init__(self, candle_interval='1m', candle_closed_only=False, depth_interval='100ms', concurrent_http=False, **kwargs):
        """
        candle_interval: str
            time between candles updates ['1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M']
        candle_closed_only: bool
            return only closed candles, i.e. no updates in between intervals.
        depth_interval: str
            time between l2_book/delta updates {'100ms', '1000ms'} (different from BINANCE_FUTURES & BINANCE_DELIVERY)
        concurrent_http: bool
            http requests will be made concurrently, if False requests will be made one at a time (affects L2_BOOK, OPEN_INTEREST).
        """
        if candle_interval not in self.valid_candle_intervals:
            raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")
        if depth_interval is not None and depth_interval not in self.valid_depth_intervals:
            raise ValueError(f"Depth interval must be one of {self.valid_depth_intervals}")

        super().__init__({}, **kwargs)
        self.ws_endpoint = 'wss://stream.binance.com:9443'
        self.rest_endpoint = 'https://www.binance.com/api/v1'
        self.candle_interval = candle_interval
        self.candle_closed_only = candle_closed_only
        self.depth_interval = depth_interval
        self.address = self._address()
        self.concurrent_http = concurrent_http

        self._open_interest_cache = {}
        self._reset()

    def _address(self) -> Union[str, Dict]:
        """
        Binance has a 200 pair/stream limit per connection, so we need to break the address
        down into multiple connections if necessary. Because the key is currently not used
        for the address dict, we can just set it to the last used stream, since this will be
        unique.

        The generic connect method supplied by Feed will take care of creating the
        correct connection objects from the addresses.
        """
        address = self.ws_endpoint + '/stream?streams='
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

        if 0 < len(subs) < 200:
            return address + '/'.join(subs)
        else:
            def split_list(_list: list, n: int):
                for i in range(0, len(_list), n):
                    yield _list[i:i + n]

            return {chunk[0]: address + '/'.join(chunk) for chunk in split_list(subs, 200)}

    def _reset(self):
        self.forced = defaultdict(bool)
        self._l2_book = {}
        self.last_update_id = {}

        if self.concurrent_http:
            # buffer 'depthUpdate' book msgs until snapshot is fetched
            self._book_buffer: Dict[str, deque[Tuple[dict, str, float]]] = {}

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
                  self.timestamp_normalize(msg['E']),
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

    def _check_update_id(self, std_pair: str, msg: dict) -> Tuple[bool, bool, bool]:
        """
        'current_match' is True if the msg's update_id matches snapshot's update_id in self.last_update_id.
        Messages will be queued (or buffered if concurrent_http is True) while fetching for snapshot, and we can return a book_callback using this msg's data instead of waiting for the next update.
        """
        skip_update = False
        forced = not self.forced[std_pair]
        current_match = msg['u'] == self.last_update_id[std_pair]

        if forced and msg['u'] <= self.last_update_id[std_pair]:
            skip_update = True
        elif forced and msg['U'] <= self.last_update_id[std_pair] + 1 <= msg['u']:
            self.last_update_id[std_pair] = msg['u']
            self.forced[std_pair] = True
        elif not forced and self.last_update_id[std_pair] + 1 == msg['U']:
            self.last_update_id[std_pair] = msg['u']
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            skip_update = True

        return skip_update, current_match

    async def _snapshot(self, pair: str) -> None:
        max_depth = self.max_depth if self.max_depth else self.valid_depths[-1]
        if max_depth not in self.valid_depths:
            for d in self.valid_depths:
                if d > max_depth:
                    max_depth = d
                    break

        url = f'{self.rest_endpoint}/depth?symbol={pair}&limit={max_depth}'
        resp = await self.http_conn.read(url)
        resp = json.loads(resp, parse_float=Decimal)

        std_pair = self.exchange_symbol_to_std_symbol(pair)
        self.last_update_id[std_pair] = resp['lastUpdateId']
        self._l2_book[std_pair] = OrderBook(self.id, std_pair, max_depth=self.max_depth, bids={Decimal(u[0]): Decimal(u[1]) for u in resp['bids']}, asks={Decimal(u[0]): Decimal(u[1]) for u in resp['asks']})
        self._l2_book[std_pair].sequence_number = resp['lastUpdateId']
        self._l2_book[std_pair].raw = resp

    async def _handle_book_msg(self, msg: dict, pair: str, timestamp: float):
        """
        Processes 'depthUpdate' update book msg. This method should only be called if pair's l2_book exists.
        """
        std_pair = self.exchange_symbol_to_std_symbol(pair)
        skip_update, current_match = self._check_update_id(std_pair, msg)
        if current_match:
            # Current msg.final_update_id == self.last_update_id[pair] which is the snapshot's update id
            return await self.book_callback(L2_BOOK, self._l2_book[std_pair], timestamp, raw=msg, sequence_number=self.last_update_id[std_pair], timestamp=self.timestamp_normalize(msg['E']))

        if skip_update:
            return

        delta = {BID: [], ASK: []}
        for s, side in (('b', BID), ('a', ASK)):
            for update in msg[s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])

                if amount == 0:
                    if price in self._l2_book[std_pair].book[side]:
                        del self._l2_book[std_pair].book[side][price]
                        delta[side].append((price, amount))
                else:
                    self._l2_book[std_pair].book[side][price] = amount
                    delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[std_pair], timestamp, timestamp=self.timestamp_normalize(msg['E']), raw=msg, delta=delta, sequence_number=self.last_update_id[std_pair])

    async def _book(self, msg: dict, pair: str, timestamp: float) -> None:
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
        book_args = (msg, pair, timestamp)
        std_pair = self.exchange_symbol_to_std_symbol(pair)

        if not self.concurrent_http:
            # handle snapshot (a)synchronously
            if std_pair not in self._l2_book:
                await self._snapshot(pair)

            return await self._handle_book_msg(*book_args)

        if std_pair in self._book_buffer:
            # snapshot is currently being fetched. std_pair will exist in self._l2_book after snapshot, but we need to continue buffering until all previous buffered messages have been processed.
            return self._book_buffer[std_pair].append(book_args)

        elif std_pair in self._l2_book:
            # snapshot exists
            return await self._handle_book_msg(*book_args)

        # Initiate buffer & get snapshot
        self._book_buffer[std_pair] = deque()
        self._book_buffer[std_pair].append(book_args)

        async def _concurrent_snapshot():
            await self._snapshot(pair)
            while len(self._book_buffer[std_pair]) > 0:
                book_args = self._book_buffer[std_pair].popleft()
                await self._handle_book_msg(*book_args)
            del self._book_buffer[std_pair]

        create_task(_concurrent_snapshot())

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
        """
        f = Funding(self.id,
                    self.exchange_symbol_to_std_symbol(msg['s']),
                    msg['p'],
                    msg['r'],
                    self.timestamp_normalize(msg['T']),
                    self.timestamp_normalize(msg['E']),
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

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']
        pair = pair.upper()
        if 'e' in msg:
            if msg['e'] == 'depthUpdate':
                await self._book(msg, pair, timestamp)
            elif msg['e'] == 'aggTrade':
                await self._trade(msg, timestamp)
            elif msg['e'] == 'forceOrder':
                await self._liquidations(msg, timestamp)
            elif msg['e'] == 'markPriceUpdate':
                await self._funding(msg, timestamp)
            elif msg['e'] == 'kline':
                await self._candle(msg, timestamp)
            else:
                LOG.warning("%s: Unexpected message received: %s", self.id, msg)
        elif 'A' in msg:
            await self._ticker(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        # Binance does not have a separate subscribe message, the
        # subscription information is included in the
        # connection endpoint
        if isinstance(conn, (HTTPPoll, HTTPConcurrentPoll)):
            self._open_interest_cache = {}
        else:
            self._reset()

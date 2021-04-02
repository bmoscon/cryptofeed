'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Union, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BINANCE, BUY, CANDLES, FUNDING, L2_BOOK, LIQUIDATIONS, OPEN_INTEREST, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize, normalize_channel


LOG = logging.getLogger('feedhandler')


class Binance(Feed):
    id = BINANCE
    valid_depths = [5, 10, 20, 50, 100, 500, 1000, 5000]
    # m -> minutes; h -> hours; d -> days; w -> weeks; M -> months
    valid_candle_intervals = {'1m', '3m', '5m', '15m', '30m', '1h', '2h', '4h', '6h', '8h', '12h', '1d', '3d', '1w', '1M'}

    def __init__(self, candle_interval='1m', candle_closed_only=False, **kwargs):
        super().__init__({}, **kwargs)
        self.ws_endpoint = 'wss://stream.binance.com:9443'
        self.rest_endpoint = 'https://www.binance.com/api/v1'
        self.candle_interval = candle_interval
        self.candle_closed_only = candle_closed_only
        if candle_interval not in self.valid_candle_intervals:
            raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")
        self.address = self._address()
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
        ret = {}
        counter = 0
        address = self.ws_endpoint + '/stream?streams='

        for chan in self.channels if not self.subscription else self.subscription:
            normalized_chan = normalize_channel(self.id, chan)

            if normalize_channel == OPEN_INTEREST:
                continue

            for pair in self.symbols if not self.subscription else self.subscription[chan]:
                if normalized_chan == CANDLES:
                    chan = f"{chan}{self.candle_interval}"

                # for everything but premium index the symbols need to be lowercase.
                if pair.startswith("p"):
                    if normalized_chan != CANDLES:
                        raise ValueError("Premium Index Symbols only allowed on Candle data feed")
                else:
                    pair = pair.lower()

                stream = f"{pair}@{chan}/"
                address += stream
                counter += 1
                if counter == 200:
                    ret[stream] = address[:-1]
                    counter = 0
                    address = self.ws_endpoint + '/stream?streams='

        if len(ret) == 0:
            if address == f"{self.ws_endpoint}/stream?streams=":
                return None
            return address[:-1]
        if counter > 0:
            ret[stream] = address[:-1]
        return ret

    def _reset(self):
        self.forced = defaultdict(bool)
        self.l2_book = {}
        self.last_update_id = {}
        self.open_interest = {}

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
        price = Decimal(msg['p'])
        amount = Decimal(msg['q'])
        await self.callback(TRADES, feed=self.id,
                            order_id=msg['a'],
                            symbol=symbol_exchange_to_std(msg['s']),
                            side=SELL if msg['m'] else BUY,
                            amount=amount,
                            price=price,
                            timestamp=timestamp_normalize(self.id, msg['E']),
                            receipt_timestamp=timestamp)

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
        pair = symbol_exchange_to_std(msg['s'])
        bid = Decimal(msg['b'])
        ask = Decimal(msg['a'])

        # Binance does not have a timestamp in this update, but the two futures APIs do
        if 'E' in msg:
            ts = timestamp_normalize(self.id, msg['E'])
        else:
            ts = timestamp

        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=bid,
                            ask=ask,
                            timestamp=ts,
                            receipt_timestamp=timestamp)

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
        pair = symbol_exchange_to_std(msg['o']['s'])
        await self.callback(LIQUIDATIONS,
                            feed=self.id,
                            symbol=pair,
                            side=msg['o']['S'],
                            leaves_qty=Decimal(msg['o']['q']),
                            price=Decimal(msg['o']['p']),
                            order_id=None,
                            timestamp=timestamp_normalize(self.id, msg['E']),
                            receipt_timestamp=timestamp)

    async def _snapshot(self, conn: AsyncConnection, pair: str) -> None:
        max_depth = self.max_depth if self.max_depth else 1000
        if max_depth not in self.valid_depths:
            for d in self.valid_depths:
                if d > max_depth:
                    max_depth = d

        url = f'{self.rest_endpoint}/depth?symbol={pair}&limit={max_depth}'
        resp = await conn.get(url)
        resp = json.loads(resp, parse_float=Decimal)

        std_pair = symbol_exchange_to_std(pair)
        self.last_update_id[std_pair] = resp['lastUpdateId']
        self.l2_book[std_pair] = {BID: sd(), ASK: sd()}
        for s, side in (('bids', BID), ('asks', ASK)):
            for update in resp[s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])
                self.l2_book[std_pair][side][price] = amount

    def _check_update_id(self, pair: str, msg: dict) -> Tuple[bool, bool]:
        skip_update = False
        forced = not self.forced[pair]

        if forced and msg['u'] <= self.last_update_id[pair]:
            skip_update = True
        elif forced and msg['U'] <= self.last_update_id[pair] + 1 <= msg['u']:
            self.last_update_id[pair] = msg['u']
            self.forced[pair] = True
        elif not forced and self.last_update_id[pair] + 1 == msg['U']:
            self.last_update_id[pair] = msg['u']
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            skip_update = True

        return skip_update, forced

    async def _book(self, conn: AsyncConnection, msg: dict, pair: str, timestamp: float):
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
        pair = symbol_exchange_to_std(pair)

        if pair not in self.l2_book:
            await self._snapshot(conn, exchange_pair)

        skip_update, forced = self._check_update_id(pair, msg)
        if skip_update:
            return

        delta = {BID: [], ASK: []}
        ts = msg['E']

        for s, side in (('b', BID), ('a', ASK)):
            for update in msg[s]:
                price = Decimal(update[0])
                amount = Decimal(update[1])

                if amount == 0:
                    if price in self.l2_book[pair][side]:
                        del self.l2_book[pair][side][price]
                        delta[side].append((price, amount))
                else:
                    self.l2_book[pair][side][price] = amount
                    delta[side].append((price, amount))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp_normalize(self.id, ts), timestamp)

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
        await self.callback(FUNDING,
                            feed=self.id,
                            symbol=symbol_exchange_to_std(msg['s']),
                            timestamp=timestamp_normalize(self.id, msg['E']),
                            receipt_timestamp=timestamp,
                            mark_price=msg['p'],
                            rate=msg['r'],
                            next_funding_time=timestamp_normalize(self.id, msg['T']),
                            )

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

        await self.callback(CANDLES,
                            feed=self.id,
                            symbol=symbol_exchange_to_std(msg['s']),
                            timestamp=timestamp_normalize(self.id, msg['E']),
                            receipt_timestamp=timestamp,
                            start=msg['k']['t'] / 1000,
                            stop=msg['k']['T'] / 1000,
                            interval=msg['k']['i'],
                            trades=msg['k']['n'],
                            open_price=Decimal(msg['k']['o']),
                            close_price=Decimal(msg['k']['c']),
                            high_price=Decimal(msg['k']['h']),
                            low_price=Decimal(msg['k']['l']),
                            volume=Decimal(msg['k']['v']),
                            closed=msg['k']['x'])

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']
        pair = pair.upper()
        if 'e' in msg:
            if msg['e'] == 'depthUpdate':
                await self._book(conn, msg, pair, timestamp)
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
        if conn.conn_type != 'https':
            self._reset()

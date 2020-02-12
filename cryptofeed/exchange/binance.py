'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json
import logging
from decimal import Decimal

import aiohttp
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import TICKER, TRADES, BUY, SELL, BID, ASK, L2_BOOK, BINANCE
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize, feed_to_exchange


LOG = logging.getLogger('feedhandler')


class Binance(Feed):
    id = BINANCE

    def __init__(self, pairs=None, channels=None, callbacks=None, depth=1000, **kwargs):
        super().__init__(None, pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.book_depth = depth
        self.ws_endpoint = 'wss://stream.binance.com:9443'
        self.rest_endpoint = 'https://www.binance.com/api/v1'
        self.address = self._address()
        self.__reset()

    def _address(self):
        address = self.ws_endpoint+'/stream?streams='
        for chan in self.channels if not self.config else self.config:
            for pair in self.pairs if not self.config else self.config[chan]:
                pair = pair.lower()
                stream = f"{pair}@{chan}/"
                address += stream
        return address[:-1]

    def __reset(self):
        self.l2_book = {}
        self.last_update_id = {}

    async def _trade(self, msg):
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
                                     pair=pair_exchange_to_std(msg['s']),
                                     side=SELL if msg['m'] else BUY,
                                     amount=amount,
                                     price=price,
                                     timestamp=timestamp_normalize(self.id, msg['E']))

    async def _ticker(self, msg):
        """
        {
        "e": "24hrTicker",  // Event type
        "E": 123456789,     // Event time
        "s": "BNBBTC",      // Symbol
        "p": "0.0015",      // Price change
        "P": "250.00",      // Price change percent
        "w": "0.0018",      // Weighted average price
        "x": "0.0009",      // Previous day's close price
        "c": "0.0025",      // Current day's close price
        "Q": "10",          // Close trade's quantity
        "b": "0.0024",      // Best bid price
        "B": "10",          // Best bid quantity
        "a": "0.0026",      // Best ask price
        "A": "100",         // Best ask quantity
        "o": "0.0010",      // Open price
        "h": "0.0025",      // High price
        "l": "0.0010",      // Low price
        "v": "10000",       // Total traded base asset volume
        "q": "18",          // Total traded quote asset volume
        "O": 0,             // Statistics open time
        "C": 86400000,      // Statistics close time
        "F": 0,             // First trade ID
        "L": 18150,         // Last trade Id
        "n": 18151          // Total number of trades
        }
        """
        pair = pair_exchange_to_std(msg['s'])
        bid = Decimal(msg['b'])
        ask = Decimal(msg['a'])
        await self.callback(TICKER, feed=self.id,
                                     pair=pair,
                                     bid=bid,
                                     ask=ask,
                                     timestamp=timestamp_normalize(self.id, msg['E']))

    async def _snapshot(self, pairs: list):
        urls = [f'{self.rest_endpoint}/depth?symbol={sym}&limit={self.book_depth}' for sym in pairs]
        async def fetch(session, url):
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()

        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(*[fetch(session, url) for url in urls])

        for r, pair in zip(results, pairs):
            std_pair = pair_exchange_to_std(pair)
            self.last_update_id[pair] = r['lastUpdateId']
            self.l2_book[std_pair] = {BID: sd(), ASK: sd()}
            for s, side in (('bids', BID), ('asks', ASK)):
                for update in r[s]:
                    price = Decimal(update[0])
                    amount = Decimal(update[1])
                    self.l2_book[std_pair][side][price] = amount

    def _check_update_id(self, pair: str, msg: dict):
        skip_update = False
        forced = False

        if pair in self.last_update_id:
            if msg['u'] <= self.last_update_id[pair]:
                skip_update = True
            elif msg['U'] <= self.last_update_id[pair]+1 <= msg['u']:
                del self.last_update_id[pair]
                forced = True
            else:
                raise Exception("Error - snaphot has no overlap with first update")

        return skip_update, forced

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
        skip_update, forced = self._check_update_id(pair, msg)
        if skip_update:
            return

        delta = {BID: [], ASK: []}
        pair = pair_exchange_to_std(pair)
        timestamp = msg['E']

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

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp_normalize(self.id, timestamp))

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']

        pair = pair.upper()

        if msg['e'] == 'depthUpdate':
            await self._book(msg, pair, timestamp)
        elif msg['e'] == 'aggTrade':
            await self._trade(msg)
        elif msg['e'] == '24hrTicker':
            await self._ticker(msg)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def subscribe(self, websocket):
        # Binance does not have a separate subscribe message, the
        # subsription information is included in the
        # connection endpoint
        self.__reset()
        # If full book enabled, collect snapshot first
        if feed_to_exchange(self.id, L2_BOOK) in self.channels:
            await self._snapshot(self.pairs)
        elif feed_to_exchange(self.id, L2_BOOK) in self.config:
            await self._snapshot(self.config[feed_to_exchange(self.id, L2_BOOK)])

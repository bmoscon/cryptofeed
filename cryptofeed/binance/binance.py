'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
import time

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import TICKER, TRADES, BUY, SELL, BID, ASK, L2_BOOK, BINANCE
from cryptofeed.standards import pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Binance(Feed):
    id = BINANCE

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(None, pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.address = self.__address()
        self.__reset()

    def __address(self):
        address = "wss://stream.binance.com:9443/stream?streams="
        for chan in self.channels:
            for pair in self.pairs:
                pair = pair.lower()
                stream = f"{pair}@{chan}/"
                address += stream
        return address[:-1]

    def __reset(self):
        self.l2_book = {}

    async def _trade(self, msg):
        """
        {
        "e": "trade",     // Event type
        "E": 123456789,   // Event time
        "s": "BNBBTC",    // Symbol
        "t": 12345,       // Trade ID
        "p": "0.001",     // Price
        "q": "100",       // Quantity
        "b": 88,          // Buyer order ID
        "a": 50,          // Seller order ID
        "T": 123456785,   // Trade time
        "m": true,        // Is the buyer the market maker?
        "M": true         // Ignore
        }
        """
        price = Decimal(msg['p'])
        amount = Decimal(msg['q'])
        await self.callbacks[TRADES](feed=self.id,
                                     order_id=msg['t'],
                                     pair=pair_exchange_to_std(msg['s']),
                                     side=SELL if msg['m'] else BUY,
                                     amount=amount,
                                     price=price,
                                     timestamp=msg['E'])

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
        await self.callbacks[TICKER](feed=self.id,
                                     pair=pair,
                                     bid=bid,
                                     ask=ask)

    async def _book(self, msg, pair):
        """
        {
        "lastUpdateId": 160,  // Last update ID
        "bids": [             // Bids to be updated
            [
            "0.0024",         // Price level to be updated
            "10",             // Quantity
            []                // Ignore
            ]
        ],
        "asks": [             // Asks to be updated
            [
            "0.0026",         // Price level to be updated
            "100",            // Quantity
            []                // Ignore
            ]
        ]
        }
        """
        self.l2_book = {
            BID: sd({Decimal(bid[0]): Decimal(bid[1]) for bid in msg['bids']}),
            ASK: sd({Decimal(ask[0]): Decimal(ask[1]) for ask in msg['asks']})
        }

        await self.callbacks[L2_BOOK](feed=self.id, pair=pair, book=self.l2_book, timestamp=time.time() * 1000)

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, event = msg['stream'].split('@')
        msg = msg['data']

        # All symbols for streams are lowercase
        pair = pair_exchange_to_std(pair.upper())

        if event == 'depth20':
            await self._book(msg, pair)
        elif msg['e'] == 'trade':
            await self._trade(msg)
        elif msg['e'] == '24hrTicker':
            await self._ticker(msg)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def subscribe(self, websocket):
        # Binance does not have a separate subscribe message, the
        # subsription information is included in the
        # connection endpoint
        pass

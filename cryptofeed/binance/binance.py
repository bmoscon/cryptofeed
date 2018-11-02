'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from cryptofeed.feed import Feed
from cryptofeed.feeds import feed_to_exchange
from cryptofeed.defines import TICKER, TRADES, L3_BOOK, BID, ASK, L2_BOOK, UND
from cryptofeed.exchanges import BINANCE
from cryptofeed.standards import pair_exchange_to_std, pair_std_to_exchange


LOG = logging.getLogger('feedhandler')


class Binance(Feed):
    id = BINANCE

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        if len(pairs) != 1:
            LOG.error("Binance requires a websocket per trading pair")
            raise ValueError("Binance requires a websocket per trading pair")
        if len(channels) != 1:
            LOG.error("Binance requires a websocket per channel pair")
            raise ValueError("Binance requires a websocket per channel pair")

        p = pair_std_to_exchange(pairs[0], BINANCE)
        c = feed_to_exchange(BINANCE, channels[0])
        endpoint = "wss://stream.binance.com:9443/ws/{}@{}".format(p.lower(), c)

        super().__init__(endpoint, None, None, callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}
        self.l3_book = {}

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
                                     side=UND,
                                     amount=amount,
                                     price=price,
                                     timestamp=msg['E'])

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['e'] == 'trade':
            await self._trade(msg)

    async def subscribe(self, websocket):
        return

'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import BITMAX
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, L2_BOOK
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize, pair_std_to_exchange


LOG = logging.getLogger('feedhandler')


class Bitmax(Feed):
    id = BITMAX

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        self.channels = None
        if pairs and len(pairs) == 1:
            self.pair = pairs[0]
            super().__init__('wss://bitmax.io/api/public/', pairs=None, channels=None, callbacks=callbacks, **kwargs)
            self.address += pair_std_to_exchange(self.pair, self.id).replace('/', '-')
            self.pairs = pairs
        else:
            self.pairs = pairs
            self.config = kwargs.get('config', None)
            self.callbacks = callbacks

    def __reset(self):
        self.l2_book = {self.pair: {BID: sd(), ASK: sd()}}

    async def subscribe(self, websocket):
        self.websocket = websocket
        self.__reset()
        await websocket.send(json.dumps(
            {
                "messageType": "subscribe",
                "marketDepthLevel": 1000,
                "recentTradeMaxCount": 1,
                "skipSummary": True,
                "skipBars": True
            }
        ))

    async def _trade(self, msg):
        for trade in msg['trades']:
            await self.callback(TRADES, feed=self.id,
                                pair=pair_exchange_to_std(msg['s']),
                                side=SELL if trade['bm'] else BUY,
                                amount=Decimal(trade['q']),
                                price=Decimal(trade['p']),
                                order_id=None,
                                timestamp=timestamp_normalize(self.id, trade['t']))

    async def _book(self, msg: dict):
        delta = {BID: [], ASK: []}
        pair = pair_exchange_to_std(msg['s'])
        for side in ('bids', 'asks'):
            for price, amount in msg[side]:
                s = BID if side == 'bids' else ASK
                price = Decimal(price)
                size = Decimal(amount)
                if size == 0:
                    delta[s].append((price, 0))
                    if price in self.l2_book[pair][s]:
                        del self.l2_book[pair][s][price]
                else:
                    delta[s].append((price, size))
                    self.l2_book[pair][s][price] = size
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, delta, timestamp_normalize(self.id, msg['ts']))

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if 'm' in msg:
            if msg['m'] == 'depth':
                await self._book(msg)
            elif msg['m'] == 'marketTrades':
                await self._trade(msg)
            elif msg['m'] == 'pong':
                return
            elif msg['m'] == 'summary':
                return
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

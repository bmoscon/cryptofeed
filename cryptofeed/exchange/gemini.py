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
from cryptofeed.defines import L2_BOOK, BUY, SELL, BID, ASK, TRADES, GEMINI
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Gemini(Feed):
    id = GEMINI

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://api.gemini.com/v2/marketdata/',
                            pairs=pairs,
                            channels=channels,
                            callbacks=callbacks,
                            **kwargs)

    def __reset(self, pairs):
        for pair in pairs:
            self.l2_book[pair_exchange_to_std(pair)] = {BID: sd(), ASK: sd()}

    async def _book(self, msg, timestamp):
        pair = pair_exchange_to_std(msg['symbol'])
        # Gemini sends ALL data for the symbol, so if we don't actually want
        # the book data, bail before parsing
        if self.channels and L2_BOOK not in self.channels:
            return
        if self.config and ((L2_BOOK in self.config and msg['symbol'] not in self.config[L2_BOOK]) or L2_BOOK not in self.config):
            return

        data = msg['changes']
        forced = not len(self.l2_book[pair][BID])
        delta = {BID: [], ASK: []}
        for entry in data:
            side = ASK if entry[0] == 'sell' else BID
            price = Decimal(entry[1])
            amount = Decimal(entry[2])
            if amount == 0:
                if price in self.l2_book[pair][side]:
                    del self.l2_book[pair][side][price]
                    delta[side].append((price, 0))
            else:
                self.l2_book[pair][side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp)

    async def _trade(self, msg, timestamp):
        pair = pair_exchange_to_std(msg['symbol'])
        price = Decimal(msg['price'])
        side = SELL if msg['side'] == 'sell' else BUY
        amount = Decimal(msg['quantity'])
        await self.callback(TRADES, feed=self.id,
                                     order_id=msg['event_id'],
                                     pair=pair,
                                     side=side,
                                     amount=amount,
                                     price=price,
                                     timestamp=timestamp_normalize(self.id, msg['timestamp']))

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['type'] == 'l2_updates':
            await self._book(msg, timestamp)
        elif msg['type'] == 'trade':
            await self._trade(msg, timestamp)
        elif msg['type'] == 'heartbeat':
            return
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    async def subscribe(self, websocket):
        pairs = self.pairs if not self.config else list(set.union(*list(self.config.values())))
        self.__reset(pairs)

        await websocket.send(json.dumps({"type": "subscribe",
                                         "subscriptions":[{"name":"l2","symbols": pairs}]}))

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
from cryptofeed.defines import TRADES, BUY, SELL, BID, ASK, TICKER, L2_BOOK, KRAKEN
from cryptofeed.standards import pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Kraken(Feed):
    id = KRAKEN

    def __init__(self, pairs=None, channels=None, callbacks=None, depth=10, **kwargs):
        super().__init__('wss://ws.kraken.com', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.book_depth = depth

    def __reset(self):
        self.l2_book = {}
        self.channel_map = {}

    async def subscribe(self, websocket):
        self.__reset()
        if self.config:
            for chan in self.config:
                sub = {"name": chan}
                if 'book' in chan:
                    sub['depth'] = self.book_depth
                await websocket.send(json.dumps({
                                        "event": "subscribe",
                                        "pair": self.config[chan],
                                        "subscription": sub
                                    }))
        else:
            for chan in self.channels:
                sub = {"name": chan}
                if 'book' in chan:
                    sub['depth'] = self.book_depth
                await websocket.send(json.dumps({
                                        "event": "subscribe",
                                        "pair": self.pairs,
                                        "subscription": sub
                                    }))

    async def _trade(self, msg, pair):
        """
        example message:

        [1,[["3417.20000","0.21222200","1549223326.971661","b","l",""]]]
        channel id, price, amount, timestamp, size, limit/market order, misc
        """
        for trade in msg[1]:
            price, amount, timestamp, side, _, _ = trade
            await self.callbacks[TRADES](feed=self.id,
                                        pair=pair,
                                        side=BUY if side == 'b' else SELL,
                                        amount=Decimal(amount),
                                        price=Decimal(price),
                                        order_id=None,
                                        timestamp=float(timestamp))

    async def _ticker(self, msg, pair):
        """
        [93, {'a': ['105.85000', 0, '0.46100000'], 'b': ['105.77000', 45, '45.00000000'], 'c': ['105.83000', '5.00000000'], 'v': ['92170.25739498', '121658.17399954'], 'p': ['107.58276', '107.95234'], 't': [4966, 6717], 'l': ['105.03000', '105.03000'], 'h': ['110.33000', '110.33000'], 'o': ['109.45000', '106.78000']}]
        channel id, asks: price, wholeLotVol, vol, bids: price, wholeLotVol, close: ...,, vol: ..., VWAP: ..., trades: ..., low: ...., high: ..., open: ...
        """
        await self.callbacks[TICKER](feed=self.id,
                                     pair=pair,
                                     bid=Decimal(msg[1]['b'][0]),
                                     ask=Decimal(msg[1]['a'][0]))

    async def _book(self, msg, pair):
        delta = {BID: [], ASK: []}
        msg = msg[1]
        if 'as' in msg:
            # Snapshot
            self.l2_book[pair] = {BID: sd({
                Decimal(update[0]): Decimal(update[1]) for update in msg['bs']
            }), ASK: sd({
                Decimal(update[0]): Decimal(update[1]) for update in msg['as']
            })}
            await self.book_callback(pair, L2_BOOK, True, delta, time.time())
        else:
            for s, updates in msg.items():
                side = BID if s == 'b' else ASK
                for update in updates:
                    price, size, _ = update
                    price = Decimal(price)
                    size = Decimal(size)
                    if size == 0:
                        # Per Kraken's technical support
                        # they deliver erroneous deletion messages
                        # periodically which should be ignored
                        if price in self.l2_book[pair][side]:
                            del self.l2_book[pair][side][price]
                            delta[side].append((price, 0))
                    else:
                        delta[side].append((price, size))
                        self.l2_book[pair][side][price] = size
                    if len(self.l2_book[pair][side]) > self.book_depth:
                        del_price = self.l2_book[pair][side].items()[0 if side == BID else -1][0]
                        del self.l2_book[pair][side][del_price]
                        delta[side].append((del_price, 0))

            await self.book_callback(pair, L2_BOOK, False, delta, time.time())

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg, list):
            if self.channel_map[msg[0]][0] == 'trade':
                await self._trade(msg, self.channel_map[msg[0]][1])
            elif self.channel_map[msg[0]][0] == 'ticker':
                await self._ticker(msg, self.channel_map[msg[0]][1])
            elif self.channel_map[msg[0]][0] == 'book':
                await self._book(msg, self.channel_map[msg[0]][1])
            else:
                LOG.warning("%s: No mapping for message %s", self.id, msg)
        else:
            if msg['event'] == 'heartbeat':
                return
            elif msg['event'] == 'systemStatus':
                return
            elif msg['event'] == 'subscriptionStatus' and msg['status'] == 'subscribed':
                self.channel_map[msg['channelID']] = (msg['subscription']['name'], pair_exchange_to_std(msg['pair']))
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)

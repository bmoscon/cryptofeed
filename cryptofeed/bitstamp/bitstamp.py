'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.defines import BUY, SELL, BID, ASK, TRADES, L2_BOOK, L3_BOOK, BITSTAMP
from cryptofeed.standards import pair_exchange_to_std, feed_to_exchange


LOG = logging.getLogger('feedhandler')


class Bitstamp(Feed):
    id = BITSTAMP
    # API documentation: https://www.bitstamp.net/websocket/v2/

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(
            'wss://ws.bitstamp.net/',
            pairs=pairs,
            channels=channels,
            callbacks=callbacks,
            **kwargs
        )

    async def _l2_book(self, msg):
        data = msg['data']
        chan = msg['channel']
        timestamp = data['timestamp']
        pair = pair_exchange_to_std(chan.split('_')[-1])

        book = {}
        for side in (BID, ASK):
            book[side] = sd({Decimal(price): Decimal(size) for price, size in data[side + 's']})
        self.l2_book[pair] = book
        await self.book_callback(pair=pair, book_type=L2_BOOK, forced=False, delta=False, timestamp=timestamp)

    async def _l3_book(self, msg):
        data = msg['data']
        chan = msg['channel']
        timestamp = data['timestamp']
        pair = pair_exchange_to_std(chan.split('_')[-1])

        book = {BID: sd(), ASK: sd()}
        for side in (BID, ASK):
            for price, size, order_id in data[side + 's']:
                price = Decimal(price)
                size = Decimal(size)
                book[side].get(price, sd())[order_id] = size
        self.l3_book[pair] = book
        await self.book_callback(pair=pair, book_type=L3_BOOK, forced=False, delta=False, timestamp=timestamp)

    async def _trades(self, msg):
        data = msg['data']
        chan = msg['channel']
        pair = pair_exchange_to_std(chan.split('_')[-1])

        side = BUY if data['type'] == 0 else SELL
        amount = Decimal(data['amount'])
        price = Decimal(data['price'])
        timestamp = data['timestamp']
        order_id = data['id']
        await self.callbacks[TRADES](feed=self.id,
                                     pair=pair,
                                     side=side,
                                     amount=amount,
                                     price=price,
                                     timestamp=timestamp,
                                     order_id=order_id
                                     )

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'bts' in msg['event']:
            if msg['event'] == 'bts:connection_established':
                pass
            elif msg['event'] == 'bts:subscription_succeeded':
                pass
            else:
                LOG.warning("%s: Unexpected message %s", self.id, msg)
        elif msg['event'] == 'trade':
            await self._trades(msg)
        elif msg['event'] == 'data':
            if msg['channel'].startswith(feed_to_exchange(self.id, L2_BOOK)):
                await self._l2_book(msg)
            if msg['channel'].startswith(feed_to_exchange(self.id, L3_BOOK)):
                await self._l3_book(msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        for channel in self.channels if not self.config else self.config:
            for pair in self.pairs if not self.config else self.config[channel]:
                await websocket.send(
                    json.dumps({
                        "event": "bts:subscribe",
                        "data": {
                            "channel": "{}_{}".format(channel, pair)
                        }
                    }))

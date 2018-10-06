'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.exchanges import BITSTAMP
from cryptofeed.feed import Feed
from cryptofeed.defines import BID, ASK, TRADES, L2_BOOK
from cryptofeed.standards import pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Bitstamp(Feed):
    id = BITSTAMP

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(
            'wss://ws.pusherapp.com/app/de504dc5763aeef9ff52?protocol=7&client=js&version=2.1.6&flash=false',
            pairs=pairs,
            channels=channels,
            callbacks=callbacks,
            **kwargs
        )

    async def _order_book(self, msg):
        data = msg['data']
        chan = msg['channel']
        timestamp = data['timestamp']
        pair = None
        if chan == 'order_book':
            pair = 'BTC-USD'
        else:
            pair = pair_exchange_to_std(chan.split('_')[-1])

        book = {}
        for side in (BID, ASK):
            book[side] = sd({price: size for price, size in data[side+'s']})
        await self.callbacks[L2_BOOK](feed=self.id, pair=pair, book=book, timestamp=timestamp)

    async def _trades(self, msg):
        data = msg['data']
        chan = msg['channel']
        pair = None
        if chan == 'live_trades':
            pair = 'BTC-USD'
        else:
            pair = pair_exchange_to_std(chan.split('_')[-1])

        side = BID if data['type'] == 0 else ASK
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
        # for some reason the internal parts of the message
        # are formatted in such a way that it wont parse from
        # string to json without stripping some extra quotes and
        # slashes
        msg = msg.replace("\\", '')
        msg = msg.replace("\"{", "{")
        msg = msg.replace("}\"", "}")
        msg = json.loads(msg, parse_float=Decimal)
        if 'pusher' in msg['event']:
            if msg['event'] == 'pusher:connection_established':
                pass
            elif msg['event'] == 'pusher_internal:subscription_succeeded':
                pass
            else:
                LOG.warning("%s: Unexpected pusher message %s", self.id, msg)
        elif msg['event'] == 'trade':
            await self._trades(msg)
        elif msg['event'] == 'data':
            await self._order_book(msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        # if channel is order book we need to subscribe to the diff channel
        # to get updates, hit the REST endpoint to get the current complete state,
        # then process the updates from the diff channel, ignoring any updates that
        # are pre-timestamp on the response from the REST endpoint
        for channel in self.channels:
            for pair in self.pairs:
                await websocket.send(
                    json.dumps({
                        "event": "pusher:subscribe",
                        "data": {
                            "channel": "{}_{}".format(channel, pair) if pair != 'btcusd' else channel
                        }
                    }))

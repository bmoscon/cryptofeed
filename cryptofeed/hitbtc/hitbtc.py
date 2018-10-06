'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
from collections import defaultdict
import time

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.exchanges import HITBTC
from cryptofeed.defines import TICKER, L2_BOOK, TRADES, BID, ASK, UPD, DEL
from cryptofeed.standards import pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class HitBTC(Feed):
    id = HITBTC

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://api.hitbtc.com/api/2/ws',
                         pairs=pairs,
                         channels=channels,
                         callbacks=callbacks,
                         **kwargs)

    async def _ticker(self, msg):
        await self.callbacks[TICKER](feed=self.id,
                                     pair=pair_exchange_to_std(msg['symbol']),
                                     bid=Decimal(msg['bid']),
                                     ask=Decimal(msg['ask']))

    async def _book(self, msg):
        timestamp = time.time()
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
        pair = pair_exchange_to_std(msg['symbol'])
        for side in (BID, ASK):
            for entry in msg[side]:
                price = Decimal(entry['price'])
                size = Decimal(entry['size'])
                if size == 0:
                    del self.l2_book[pair][side][price]
                    delta[side][DEL].append(price)
                else:
                    self.l2_book[pair][side][price] = size
                    delta[side][UPD].append((price, size))
        await self.book_callback(pair, L2_BOOK, False, delta, timestamp)

    async def _snapshot(self, msg):
        timestamp = time.time()
        pair = pair_exchange_to_std(msg['symbol'])
        self.l2_book[pair] = {ASK: sd(), BID: sd()}
        for side in (BID, ASK):
            for entry in msg[side]:
                price = Decimal(entry['price'])
                size = Decimal(entry['size'])
                self.l2_book[pair][side][price] = size
        await self.book_callback(pair, L2_BOOK, True, None, timestamp)

    async def _trades(self, msg):
        pair = pair_exchange_to_std(msg['symbol'])
        for update in msg['data']:
            price = Decimal(update['price'])
            quantity = Decimal(update['quantity'])
            side = update['side']
            order_id = update['id']
            timestamp = update['timestamp']
            await self.callbacks[TRADES](feed=self.id,
                                         pair=pair,
                                         side=side,
                                         amount=quantity,
                                         price=price,
                                         order_id=order_id,
                                         timestamp=timestamp)

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'method' in msg:
            if msg['method'] == 'ticker':
                await self._ticker(msg['params'])
            elif msg['method'] == 'snapshotOrderbook':
                await self._snapshot(msg['params'])
            elif msg['method'] == 'updateOrderbook':
                await self._book(msg['params'])
            elif msg['method'] == 'updateTrades' or msg['method'] == 'snapshotTrades':
                await self._trades(msg['params'])
            else:
                LOG.warning("%s: Invalid message received: %s", self.id, msg)
        elif 'channel' in msg:
            if msg['channel'] == 'ticker':
                await self._ticker(msg['data'])
            else:
                LOG.warning("%s: Invalid message received: %s", self.id, msg)
        else:
            if 'error' in msg or not msg['result']:
                LOG.error("%s: Received error from server: %s", self.id, msg)

    async def subscribe(self, websocket):
        for channel in self.channels:
            for pair in self.pairs:
                await websocket.send(
                    json.dumps({
                        "method": channel,
                        "params": {
                            "symbol": pair
                        },
                        "id": 123
                    }))

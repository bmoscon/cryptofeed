'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.callback import Callback
from cryptofeed.exchanges import HITBTC
from cryptofeed.defines import TICKER, L3_BOOK, TRADES, BID, ASK
from cryptofeed.standards import pair_exchange_to_std


LOG = logging.getLogger('feedhandler')


class HitBTC(Feed):
    id = HITBTC

    def __init__(self, pairs=None, channels=None, callbacks=None):
        super().__init__('wss://api.hitbtc.com/api/2/ws',
                         pairs=pairs,
                         channels=channels,
                         callbacks=callbacks)

    async def _ticker(self, msg):
        await self.callbacks[TICKER](feed=self.id,
                                     pair=pair_exchange_to_std(msg['symbol']),
                                     bid=Decimal(msg['bid']),
                                     ask=Decimal(msg['ask']))
    
    async def _book(self, msg):
        pair = pair_exchange_to_std(msg['symbol'])
        for side in (BID, ASK):
            for entry in msg[side]:
                price = Decimal(entry['price'])
                size = Decimal(entry['size'])
                if size == 0:
                    del self.l3_book[pair][side][price]
                else:
                    self.l3_book[pair][side][price] = size
        await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.l3_book[pair])

    async def _snapshot(self, msg):
        pair = pair_exchange_to_std(msg['symbol'])
        self.l3_book[pair] = {ASK: sd(), BID: sd()}
        for side in (BID, ASK):
            for entry in msg[side]:
                price = Decimal(entry['price'])
                size = Decimal(entry['size'])
                self.l3_book[pair][side][price] = size
        await self.callbacks[L3_BOOK](feed=self.id, pair=pair, book=self.l3_book[pair])

    async def _trades(self, msg):
        pair = pair_exchange_to_std(msg['symbol'])
        for update in msg['data']:
            price = Decimal(update['price'])
            quantity = Decimal(update['quantity'])
            side = update['side']
            await self.callbacks[TRADES](feed=self.id,
                                         pair=pair,
                                         side=side,
                                         amount=quantity,
                                         price=price)

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
                LOG.warning("{} - Invalid message received: {}".format(self.id, msg))
        elif 'channel' in msg:
            if msg['channel'] == 'ticker':
                await self._ticker(msg['data'])
            else:
                LOG.warning("{} - Invalid message received: {}".format(self.id, msg))
        else:
            if 'error' in msg or not msg['result']:
                LOG.error("{} - Received error from server {}".format(self.id, msg))

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

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
from cryptofeed.defines import TICKER, L2_BOOK, TRADES, BUY, SELL, BID, ASK, HITBTC
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


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
        await self.callback(TICKER, feed=self.id,
                                     pair=pair_exchange_to_std(msg['symbol']),
                                     bid=Decimal(msg['bid']),
                                     ask=Decimal(msg['ask']),
                                     timestamp=timestamp_normalize(self.id, msg['timestamp']))

    async def _book(self, msg: dict, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = pair_exchange_to_std(msg['symbol'])
        for side in (BID, ASK):
            for entry in msg[side]:
                price = Decimal(entry['price'])
                size = Decimal(entry['size'])
                if size == 0:
                    if price in self.l2_book[pair][side]:
                        del self.l2_book[pair][side][price]
                    delta[side].append((price, 0))
                else:
                    self.l2_book[pair][side][price] = size
                    delta[side].append((price, size))
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp)

    async def _snapshot(self, msg: dict, timestamp: float):
        pair = pair_exchange_to_std(msg['symbol'])
        self.l2_book[pair] = {ASK: sd(), BID: sd()}
        for side in (BID, ASK):
            for entry in msg[side]:
                price = Decimal(entry['price'])
                size = Decimal(entry['size'])
                self.l2_book[pair][side][price] = size
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp)

    async def _trades(self, msg):
        pair = pair_exchange_to_std(msg['symbol'])
        for update in msg['data']:
            price = Decimal(update['price'])
            quantity = Decimal(update['quantity'])
            side = BUY if update['side'] == 'buy' else SELL
            order_id = update['id']
            timestamp = timestamp_normalize(self.id, update['timestamp'])
            await self.callback(TRADES, feed=self.id,
                                         pair=pair,
                                         side=side,
                                         amount=quantity,
                                         price=price,
                                         order_id=order_id,
                                         timestamp=timestamp)

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if 'method' in msg:
            if msg['method'] == 'ticker':
                await self._ticker(msg['params'])
            elif msg['method'] == 'snapshotOrderbook':
                await self._snapshot(msg['params'], timestamp)
            elif msg['method'] == 'updateOrderbook':
                await self._book(msg['params'], timestamp)
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
        for channel in self.channels if not self.config else self.config:
            for pair in self.pairs if not self.config else self.config[channel]:
                await websocket.send(
                    json.dumps({
                        "method": channel,
                        "params": {
                            "symbol": pair
                        },
                        "id": 123
                    }))

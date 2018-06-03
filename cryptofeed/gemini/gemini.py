'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
import asyncio
from decimal import Decimal
from functools import partial

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.exchanges import GEMINI
from cryptofeed.defines import L3_BOOK_UPDATE, L3_BOOK, BID, ASK, TRADES
from cryptofeed.standards import pair_std_to_exchange


LOG = logging.getLogger('feedhandler')


class Gemini(Feed):
    id = GEMINI

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        self.l3_snapshot_channel = False
        if len(pairs) != 1:
            LOG.error("Gemini requires a websocket per trading pair")
            raise ValueError("Gemini requires a websocket per trading pair")
        if channels == [L3_BOOK]:
            self.l3_snapshot_channel = True
            channels = None
        if channels is not None:
            LOG.error("Gemini does not support different channels")
            raise ValueError("Gemini does not support different channels")
        self.pair = pairs[0]
        self.exchange_pair = pair_std_to_exchange(pairs[0], 'GEMINI')

        super().__init__('wss://api.gemini.com/v1/marketdata/' + self.exchange_pair,
                         pairs=None,
                         channels=None,
                         callbacks=callbacks,
                         **kwargs)
        self.book = {BID: sd(), ASK: sd()}

    async def _book_snapshot(self):
        loop = asyncio.get_event_loop()
        url = 'https://api.gemini.com/v1/book/{}'.format(self.exchange_pair)
        # set limits to 0 to get whole book
        get_book = partial(requests.get, params={'limit_bids': 0, 'limit_asks': 0})
        response = await loop.run_in_executor(None, get_book, url)
        response = response.json()
        snapshot = {BID: sd(), ASK: sd()}
        for side in (BID, ASK):
            book_side = snapshot[side]
            msg_book_side = response[side + 's']
            for level in msg_book_side:
                price = Decimal(level['price'])
                size = Decimal(level['amount'])
                book_side[price] = size
        msg = {'timestamp': None,
               'type': 'l3snapshot',
               'book': snapshot}

        return json.dumps(msg)

    async def _l3_snapshot(self, msg):
        msg.pop('type', None)
        timestamp = msg.pop('timestamp', None)
        book = msg.pop('book')
        await self.callbacks[L3_BOOK](feed=self.id, pair=self.pair, timestamp=timestamp, sequence=None, book=book)

    async def _book(self, msg):
        sequence = msg['sequence']
        side = BID if msg['side'] == 'bid' else ASK
        price = Decimal(msg['price'])
        remaining = Decimal(msg['remaining'])
        delta = Decimal(msg['delta'])
        reason = msg['reason']
        timestamp = msg['timestamp']

        if msg['reason'] == 'initial':
            self.book[side][price] = remaining
        else:
            if remaining == 0:
                del self.book[side][price]
            else:
                self.book[side][price] = remaining
        await self.callbacks[L3_BOOK_UPDATE](feed=self.id, pair=self.pair, msg_type=reason, ts=timestamp,
                                             seq=sequence, side=side, price=price, size=delta)

    async def _trade(self, msg):
        price = Decimal(msg['price'])
        side = BID if msg['makerSide'] == 'bid' else ASK
        amount = Decimal(msg['amount'])
        await self.callbacks[TRADES](feed=self.id, id=msg['tid'], pair=self.pair,
                                     side=side, amount=amount, price=price)

    async def _update(self, msg):
        sequence = msg['socket_sequence']
        # print(msg)
        # timstamp data only provided after initial book snapshot is provided, snapshot is socket_sequence = 0
        if sequence is not 0:
            timestamp = (Decimal(msg['timestampms'])/Decimal(1000)) if msg.get('timestampms') else Decimal(msg['timestamp'])
        else:
            timestamp = None
        for update in msg['events']:
            update['timestamp'] = timestamp
            update['sequence'] = sequence
            if update['type'] == 'change':
                await self._book(update)
            elif update['type'] == 'trade':
                await self._trade(update)
            elif update['type'] == 'auction':
                pass
            elif update['type'] == 'block_trade':
                pass
            else:
                LOG.warning("Invalid update received {}".format(update))

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if msg['type'] == 'update':
            await self._update(msg)
        elif msg['type'] == 'heartbeat':
            pass
        elif msg['type'] == 'l3snapshot':
            await self._l3_snapshot(msg)
        else:
            LOG.warning('Invalid message type {}'.format(msg))

    async def subscribe(self, *args):
        if self.l3_snapshot_channel:
            asyncio.ensure_future(self.synthesize_feed(self._book_snapshot))

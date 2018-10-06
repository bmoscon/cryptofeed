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
from cryptofeed.exchanges import GEMINI
from cryptofeed.defines import L2_BOOK, BID, ASK, TRADES, UPD, DEL
from cryptofeed.standards import pair_std_to_exchange
from cryptofeed.exceptions import MissingSequenceNumber


LOG = logging.getLogger('feedhandler')


class Gemini(Feed):
    id = GEMINI

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        if len(pairs) != 1:
            LOG.error("Gemini requires a websocket per trading pair")
            raise ValueError("Gemini requires a websocket per trading pair")
        if channels is not None:
            LOG.error("Gemini does not support different channels")
            raise ValueError("Gemini does not support different channels")
        self.pair = pairs[0]

        super().__init__('wss://api.gemini.com/v1/marketdata/' + pair_std_to_exchange(self.pair, 'GEMINI'),
                         pairs=None,
                         channels=None,
                         callbacks=callbacks,
                         **kwargs)
        self.l2_book = {self.pair: {BID: sd(), ASK: sd()}}
        self.seq_no = None

    async def _book(self, msg, timestamp):
        delta = {BID: {}, ASK: {}}
        side = BID if msg['side'] == 'bid' else ASK
        price = Decimal(msg['price'])
        remaining = Decimal(msg['remaining'])
        #delta = Decimal(msg['delta'])

        if msg['reason'] == 'initial':
            self.l2_book[self.pair][side][price] = remaining
        else:
            if remaining == 0:
                del self.l2_book[self.pair][side][price]
                delta[side][DEL] = [price]
            else:
                self.l2_book[self.pair][side][price] = remaining
                delta[side][UPD] = [(price, remaining)]
            await self.book_callback(self.pair, L2_BOOK, False, delta, timestamp)

    async def _trade(self, msg, timestamp):
        price = Decimal(msg['price'])
        side = BID if msg['makerSide'] == 'bid' else ASK
        amount = Decimal(msg['amount'])
        await self.callbacks[TRADES](feed=self.id,
                                     order_id=msg['tid'],
                                     pair=self.pair,
                                     side=side,
                                     amount=amount,
                                     price=price,
                                     timestamp=timestamp)

    async def _update(self, msg):
        timestamp = None
        if 'timestampms' in msg:
            timestamp = msg['timestampms'] / 1000.0
        forced = False
        for update in msg['events']:
            if update['type'] == 'change':
                await self._book(update, timestamp)
                if update['reason'] == 'initial':
                    forced = True
            elif update['type'] == 'trade':
                await self._trade(update, timestamp)
            elif update['type'] == 'auction':
                pass
            elif update['type'] == 'block_trade':
                pass
            else:
                LOG.warning("%s: Invalid update received %s", self.id, update)
        if forced:
            await self.book_callback(self.pair, L2_BOOK, True, None, timestamp)


    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        seq_no = msg['socket_sequence']

        if self.seq_no and self.seq_no + 1 != seq_no:
            LOG.warning("%s: missing sequence number. Received %d, expected %d", self.id, seq_no, self.seq_no+1)
            raise MissingSequenceNumber
        else:
            self.seq_no = seq_no
        if msg['type'] == 'update':
            await self._update(msg)
        elif msg['type'] == 'heartbeat':
            pass
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    async def subscribe(self, *args):
        return

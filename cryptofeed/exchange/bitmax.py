'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import BID, ASK, BITMAX, BUY, L2_BOOK, SELL, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Bitmax(Feed):
    id = BITMAX

    def __init__(self, **kwargs):
        super().__init__('wss://bitmax.io/0/api/pro/v1/stream', **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}
        self.seq_no = defaultdict(lambda: None)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'm': 'trades',
            'symbol': 'BTC/USDT',
            'data': [{
                'p': '23169.76',
                'q': '0.00899',
                'ts': 1608760026461,
                'bm': False,
                'seqnum': 72057614186183012
            }]
        }
        """
        for trade in msg['data']:
            await self.callback(TRADES, feed=self.id,
                                symbol=symbol_exchange_to_std(msg['symbol']),
                                side=SELL if trade['bm'] else BUY,
                                amount=Decimal(trade['q']),
                                price=Decimal(trade['p']),
                                order_id=None,
                                timestamp=timestamp_normalize(self.id, trade['ts']),
                                receipt_timestamp=timestamp)

    async def _book(self, msg: dict, timestamp: float):
        sequence_number = msg['data']['seqnum']
        pair = symbol_exchange_to_std(msg['symbol'])
        delta = {BID: [], ASK: []}
        forced = False

        if msg['m'] == 'depth-snapshot':
            forced = True
            self.seq_no[pair] = sequence_number
            self.l2_book[pair] = {BID: sd(), ASK: sd()}
        else:
            # ignore messages while we wait for the snapshot
            if self.seq_no[pair] is None:
                return
            if self.seq_no[pair] + 1 != sequence_number:
                raise MissingSequenceNumber
            self.seq_no[pair] = sequence_number

        for side in ('bids', 'asks'):
            for price, amount in msg['data'][side]:
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

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp_normalize(self.id, msg['data']['ts']), timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if 'm' in msg:
            if msg['m'] == 'depth' or msg['m'] == 'depth-snapshot':
                await self._book(msg, timestamp)
            elif msg['m'] == 'trades':
                await self._trade(msg, timestamp)
            elif msg['m'] == 'ping':
                await conn.send('{"op":"pong"}')
            elif msg['m'] == 'connected':
                return
            elif msg['m'] == 'sub':
                return
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, websocket):
        self.__reset()
        l2_pairs = []

        for channel in self.channels if not self.subscription else self.subscription:
            pairs = self.symbols if not self.subscription else self.subscription[channel]

            if channel == "depth:":
                l2_pairs.extend(pairs)

            pairs = self.symbols if not self.subscription else self.subscription[channel]
            message = {'op': 'sub', 'ch': channel + ','.join(pairs)}
            await websocket.send(json.dumps(message))

        for pair in l2_pairs:
            message = {"op": "req", "action": "depth-snapshot", "args": {"symbol": pair}}
            await websocket.send(json.dumps(message))

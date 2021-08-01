'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from typing import Dict, Tuple
from cryptofeed.connection import AsyncConnection
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import ASCENDEX, BID, ASK, BUY, L2_BOOK, SELL, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol


LOG = logging.getLogger('feedhandler')


class AscendEX(Feed):
    id = ASCENDEX
    symbol_endpoint = 'https://ascendex.com/api/pro/v1/products'
    websocket_channels = {
        L2_BOOK: 'depth:',
        TRADES: 'trades:',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']:
            # Only "Normal" status symbols are tradeable
            if entry['status'] == 'Normal':
                s = Symbol(entry['baseAsset'], entry['quoteAsset'])
                ret[s.normalized] = entry['symbol']
                info['tick_size'][s.normalized] = entry['tickSize']
                info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://ascendex.com/1/api/pro/v1/stream', **kwargs)
        self.__reset()

    def __reset(self):
        self._l2_book = {}
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
                                symbol=self.exchange_symbol_to_std_symbol(msg['symbol']),
                                side=SELL if trade['bm'] else BUY,
                                amount=Decimal(trade['q']),
                                price=Decimal(trade['p']),
                                order_id=None,
                                timestamp=self.timestamp_normalize(trade['ts']),
                                receipt_timestamp=timestamp)

    async def _book(self, msg: dict, timestamp: float):
        sequence_number = msg['data']['seqnum']
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        delta = {BID: [], ASK: []}
        forced = False

        if msg['m'] == 'depth-snapshot':
            forced = True
            self.seq_no[pair] = sequence_number
            self._l2_book[pair] = {BID: sd(), ASK: sd()}
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
                    if price in self._l2_book[pair][s]:
                        del self._l2_book[pair][s][price]
                else:
                    delta[s].append((price, size))
                    self._l2_book[pair][s][price] = size

        await self.book_callback(self._l2_book[pair], L2_BOOK, pair, forced, delta, self.timestamp_normalize(msg['data']['ts']), timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if 'm' in msg:
            if msg['m'] == 'depth' or msg['m'] == 'depth-snapshot':
                await self._book(msg, timestamp)
            elif msg['m'] == 'trades':
                await self._trade(msg, timestamp)
            elif msg['m'] == 'ping':
                await conn.write('{"op":"pong"}')
            elif msg['m'] == 'connected':
                return
            elif msg['m'] == 'sub':
                return
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        l2_pairs = []

        for channel in self.subscription:
            pairs = self.subscription[channel]

            if channel == "depth:":
                l2_pairs.extend(pairs)

            message = {'op': 'sub', 'ch': channel + ','.join(pairs)}
            await conn.write(json.dumps(message))

        for pair in l2_pairs:
            message = {"op": "req", "action": "depth-snapshot", "args": {"symbol": pair}}
            await conn.write(json.dumps(message))

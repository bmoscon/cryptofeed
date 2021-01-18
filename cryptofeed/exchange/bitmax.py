'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import random
from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, List, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BITMAX, BUY, L2_BOOK, SELL, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize
from cryptofeed.util import split

LOG = logging.getLogger('feedhandler')


class Bitmax(Feed):
    id = BITMAX

    def __init__(self, **kwargs):
        super().__init__('wss://bitmax.io/0/api/pro/v1/stream', **kwargs)
        self.__reset()
        self.address = self._address('wss://bitmax.io/0/api/pro/v1/stream')

    def __reset(self):
        # TODO: store context data in conn.ctx
        self.l2_book = {}
        self.seq_no = defaultdict(lambda: None)

    def _address(self, ws_endpoint: str) -> Dict[Tuple[Tuple[str, str]], str]:
        """
        When 11 pair-channels in one subscribe msg, BITMAX responds
        "Invalid operation: No more than 10 symbols per subscribe operation.".
        When sending multiple "sub" messages in the same websocket, BITMAX responds the same error.
        """
        pair_channels: List[Tuple[str, str]] = []
        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                pair_channels.append((pair, chan))

        # mix pair/channel combinations to avoid having most of the BTC & USD pairs in the same websocket
        random.shuffle(pair_channels)

        address: Dict[Tuple[Tuple[str, str]], str] = {}
        for chunk in split.list_by_max_items(pair_channels, 10):
            address[tuple(chunk)] = ws_endpoint
        LOG.info("%s: prepared %s WS subscriptions using %s", self.id, len(address), ws_endpoint)
        return address

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

    async def handle(self, data: bytes, timestamp: float, conn: AsyncConnection):
        """
        {'m': 'depth', 'ts': 0, 'seqnum': 0, 's': 'ETH/PAX', 'asks': [], 'bids': []}
        """
        assert isinstance(conn, WSAsyncConn)

        msg = json.loads(data, parse_float=Decimal)

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
                LOG.warning("%s: Invalid message type %s", conn.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", conn.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        assert isinstance(conn, WSAsyncConn)
        assert 'opt' in conn.ctx
        assert isinstance(conn.ctx['opt'], tuple)
        opt: Tuple[Tuple[str, str]] = conn.ctx['opt']
        self.__reset()

        assert opt
        for symbol, chan in opt:
            if chan == "depth:":
                message = {"op": "req", "action": "depth-snapshot", "args": {"symbol": symbol}}
            else:
                message = {'op': 'sub', 'ch': chan + symbol}
            await conn.send(json.dumps(message))

        # # Fallback if options is None
        # for chan in set(self.channels or self.subscription):
        #     symbols = set(self.symbols or self.subscription[chan])
        #     for chunk in split.list_by_max_items(symbols, 10):
        #         message = {'op': 'sub', 'ch': chan + ','.join(chunk)}
        #         await conn.send(json.dumps(message))
        #     if chan == "depth:":
        #         for symbol in symbols:
        #             message = {"op": "req", "action": "depth-snapshot", "args": {"symbol": symbol}}
        #             await conn.send(json.dumps(message))

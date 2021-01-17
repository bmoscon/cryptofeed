'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, HITBTC, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class HitBTC(Feed):
    id = HITBTC

    def __init__(self, **kwargs):
        super().__init__('wss://api.hitbtc.com/api/2/ws', **kwargs)
        self.seq_no = {}

    async def _ticker(self, msg: dict, timestamp: float):
        await self.callback(TICKER, feed=self.id,
                            symbol=symbol_exchange_to_std(msg['symbol']),
                            bid=Decimal(msg['bid']),
                            ask=Decimal(msg['ask']),
                            timestamp=timestamp_normalize(self.id, msg['timestamp']),
                            receipt_timestamp=timestamp)

    async def _book(self, msg: dict, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = symbol_exchange_to_std(msg['symbol'])
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
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp, timestamp)

    async def _snapshot(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['symbol'])
        self.l2_book[pair] = {ASK: sd(), BID: sd()}
        for side in (BID, ASK):
            for entry in msg[side]:
                price = Decimal(entry['price'])
                size = Decimal(entry['size'])
                self.l2_book[pair][side][price] = size
        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp, timestamp)

    async def _trades(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['symbol'])
        for update in msg['data']:
            price = Decimal(update['price'])
            quantity = Decimal(update['quantity'])
            side = BUY if update['side'] == 'buy' else SELL
            order_id = update['id']
            timestamp = timestamp_normalize(self.id, update['timestamp'])
            await self.callback(TRADES, feed=self.id,
                                symbol=pair,
                                side=side,
                                amount=quantity,
                                price=price,
                                order_id=order_id,
                                timestamp=timestamp,
                                receipt_timestamp=timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)
        if 'params' in msg and 'sequence' in msg['params']:
            pair = msg['params']['symbol']
            if pair in self.seq_no:
                if self.seq_no[pair] + 1 != msg['params']['sequence']:
                    LOG.warning("%s: Missing sequence number detected for %s", self.id, pair)
                    raise MissingSequenceNumber("Missing sequence number, restarting")
            self.seq_no[pair] = msg['params']['sequence']

        if 'method' in msg:
            if msg['method'] == 'ticker':
                await self._ticker(msg['params'], timestamp)
            elif msg['method'] == 'snapshotOrderbook':
                await self._snapshot(msg['params'], timestamp)
            elif msg['method'] == 'updateOrderbook':
                await self._book(msg['params'], timestamp)
            elif msg['method'] == 'updateTrades' or msg['method'] == 'snapshotTrades':
                await self._trades(msg['params'], timestamp)
            else:
                LOG.warning("%s: Invalid message received: %s", self.id, msg)
        elif 'channel' in msg:
            if msg['channel'] == 'ticker':
                await self._ticker(msg['data'], timestamp)
            else:
                LOG.warning("%s: Invalid message received: %s", self.id, msg)
        else:
            if 'error' in msg or not msg['result']:
                LOG.error("%s: Received error from server: %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                await conn.send(
                    json.dumps({
                        "method": chan,
                        "params": {
                            "symbol": pair
                        },
                        "id": conn.uuid
                    }))

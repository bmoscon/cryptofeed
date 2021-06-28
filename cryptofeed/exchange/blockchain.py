'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BLOCKCHAIN, BUY, L2_BOOK, L3_BOOK, SELL, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Blockchain(Feed):
    id = BLOCKCHAIN
    symbol_endpoint = "https://api.blockchain.com/mercury-gateway/v1/instruments"

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        return {data["symbol"].replace("-", symbol_separator): data["symbol"] for data in data if data['status'] == 'open'}, {}

    def __init__(self, **kwargs):
        super().__init__("wss://ws.prod.blockchain.info/mercury-gateway/v1/ws", origin="https://exchange.blockchain.com", **kwargs)
        self.__reset()

    def __reset(self):
        self.seq_no = None
        self.l2_book = {}
        self.l3_book = {}

    async def _pair_l2_update(self, msg: str, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        forced = False
        if msg['event'] == 'snapshot':
            # Reset the book
            self.l2_book[pair] = {BID: sd(), ASK: sd()}
            forced = True
        book = self.l2_book[pair]

        for side in (BID, ASK):
            for update in msg[side + 's']:
                price = update['px']
                qty = update['qty']
                book[side][price] = qty
                if qty <= 0:
                    del book[side][price]
                delta[side].append((price, qty))

        self.l2_book[pair] = book

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def _handle_l2_msg(self, msg: str, timestamp: float):
        """
        Subscribed message
        {
          "seqnum": 1,
          "event": "subscribed",
          "channel": "l2",
          "symbol": "BTC-USD"
        }

        """

        if msg['event'] == 'subscribed':
            LOG.info("%s: Subscribed to L2 data for %s", self.id, msg['symbol'])
        elif msg['event'] in ['snapshot', 'updated']:
            await self._pair_l2_update(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message %s", self.id, msg)

    async def _pair_l3_update(self, msg: str, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])

        if msg['event'] == 'snapshot':
            # Reset the book
            self.l3_book[pair] = {BID: sd(), ASK: sd()}

        book = self.l3_book[pair]

        for side in (BID, ASK):
            for update in msg[side + 's']:
                price = update['px']
                qty = update['qty']
                order_id = update['id']

                p_orders = book[side].get(price, sd())
                p_orders[order_id] = qty
                if qty <= 0:
                    del p_orders[order_id]

                book[side][price] = p_orders
                if len(book[side][price]) == 0:
                    del book[side][price]

                delta[side].append((order_id, price, qty))

        self.l3_book[pair] = book

        await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, timestamp, timestamp)

    async def _handle_l3_msg(self, msg: str, timestamp: float):
        if msg['event'] == 'subscribed':
            LOG.info("%s: Subscribed to L3 data for %s", self.id, msg['symbol'])
        elif msg['event'] in ['snapshot', 'updated']:
            await self._pair_l3_update(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message %s", self.id, msg)

    async def _trade(self, msg: dict, timestamp: float):
        """
        trade msg example

        {
          "seqnum": 21,
          "event": "updated",
          "channel": "trades",
          "symbol": "BTC-USD",
          "timestamp": "2019-08-13T11:30:06.100140Z",
          "side": "sell",
          "qty": 8.5E-5,
          "price": 11252.4,
          "trade_id": "12884909920"
        }
        """
        await self.callback(TRADES, feed=self.id,
                            symbol=msg['symbol'],
                            side=BUY if msg['side'] == 'buy' else SELL,
                            amount=msg['qty'],
                            price=msg['price'],
                            order_id=msg['trade_id'],
                            timestamp=timestamp_normalize(self.id, msg['timestamp']),
                            receipt_timestamp=timestamp)

    async def _handle_trade_msg(self, msg: str, timestamp: float):
        if msg['event'] == 'subscribed':
            LOG.info("%s: Subscribed to trades channel for %s", self.id, msg['symbol'])
        elif msg['event'] == 'updated':
            await self._trade(msg, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if self.seq_no is not None and msg['seqnum'] != self.seq_no + 1:
            LOG.warning("%s: Missing sequence number detected!", self.id)
            raise MissingSequenceNumber("Missing sequence number, restarting")

        self.seq_no = msg['seqnum']

        if 'channel' in msg:
            if msg['channel'] == 'l2':
                await self._handle_l2_msg(msg, timestamp)
            elif msg['channel'] == 'l3':
                await self._handle_l3_msg(msg, timestamp)
            elif msg['channel'] == 'trades':
                await self._handle_trade_msg(msg, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                await conn.write(json.dumps({"action": "subscribe",
                                             "symbol": pair,
                                             "channel": chan
                                             }))

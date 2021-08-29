'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BLOCKCHAIN, BUY, L2_BOOK, L3_BOOK, SELL, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade


LOG = logging.getLogger('feedhandler')


class Blockchain(Feed):
    id = BLOCKCHAIN
    symbol_endpoint = "https://api.blockchain.com/mercury-gateway/v1/instruments"
    websocket_channels = {
        L3_BOOK: 'l3',
        L2_BOOK: 'l2',
        TRADES: 'trades',
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        info = {'instrument_type': {}}
        ret = {}
        for entry in data:
            if entry['status'] != 'open':
                continue
            base, quote = entry['symbol'].split("-")
            s = Symbol(base, quote)
            ret[s.normalized] = entry['symbol']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __init__(self, **kwargs):
        super().__init__("wss://ws.prod.blockchain.info/mercury-gateway/v1/ws", origin="https://exchange.blockchain.com", **kwargs)
        self.__reset()

    def __reset(self):
        self.seq_no = None
        self._l2_book = {}
        self._l3_book = {}

    async def _pair_l2_update(self, msg: str, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])
        if msg['event'] == 'snapshot':
            # Reset the book
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)

        for side in (BID, ASK):
            for update in msg[side + 's']:
                price = update['px']
                qty = update['qty']
                self._l2_book[pair].book[side][price] = qty
                if qty <= 0:
                    del self._l2_book[pair].book[side][price]
                delta[side].append((price, qty))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg, delta=delta if msg['event'] != 'snapshot' else None, sequence_number=msg['seqnum'])

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
            LOG.debug("%s: Subscribed to L2 data for %s", self.id, msg['symbol'])
        elif msg['event'] in ['snapshot', 'updated']:
            await self._pair_l2_update(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message %s", self.id, msg)

    async def _pair_l3_update(self, msg: str, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = self.exchange_symbol_to_std_symbol(msg['symbol'])

        if msg['event'] == 'snapshot':
            # Reset the book
            self._l3_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)

        for side in (BID, ASK):
            for update in msg[side + 's']:
                price = update['px']
                qty = update['qty']
                order_id = update['id']

                if qty <= 0:
                    del self._l3_book[pair].book[side][price][order_id]
                else:
                    if price in self._l3_book[pair].book[side]:
                        self._l3_book[pair].book[side][price][order_id] = qty
                    else:
                        self._l3_book[pair].book[side][price] = {order_id: qty}

                if len(self._l3_book[pair].book[side][price]) == 0:
                    del self._l3_book[pair].book[side][price]

                delta[side].append((order_id, price, qty))

        await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, raw=msg, delta=delta if msg['event'] != 'snapshot' else None, sequence_number=msg['seqnum'])

    async def _handle_l3_msg(self, msg: str, timestamp: float):
        if msg['event'] == 'subscribed':
            LOG.debug("%s: Subscribed to L3 data for %s", self.id, msg['symbol'])
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
        t = Trade(
            self.id,
            msg['symbol'],
            BUY if msg['side'] == 'buy' else SELL,
            msg['qty'],
            msg['price'],
            self.timestamp_normalize(msg['timestamp']),
            id=msg['trade_id'],
        )
        await self.callback(TRADES, t, timestamp)

    async def _handle_trade_msg(self, msg: str, timestamp: float):
        if msg['event'] == 'subscribed':
            LOG.debug("%s: Subscribed to trades channel for %s", self.id, msg['symbol'])
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

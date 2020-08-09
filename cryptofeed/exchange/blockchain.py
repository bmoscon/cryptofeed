'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
from itertools import product

from sortedcontainers import SortedDict as sd

from cryptofeed.defines import BID, ASK, BLOCKCHAIN, BUY, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Blockchain(Feed):
    id = BLOCKCHAIN

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__("wss://ws.prod.blockchain.info/mercury-gateway/v1/ws",
                         pairs=pairs, channels=channels, callbacks=callbacks,
                         origin="https://exchange.blockchain.com",
                         **kwargs)
        self.__reset()

    def __reset(self):
        self.seq_no = None
        self.l2_book = {}
        self.l3_book = {}

    async def _pair_l2_update(self, msg: str, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = pair_exchange_to_std(msg['symbol'])
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

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair,
                                 forced, delta, timestamp_normalize(self.id, timestamp), timestamp)

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
            LOG.info(f"Subscribed to {msg['symbol']}")
        elif msg['event'] in ['snapshot', 'updated']:
            await self._pair_l2_update(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message %s", self.id, msg)

    async def _pair_l3_update(self, msg: str, timestamp: float):
        delta = {BID: [], ASK: []}
        pair = pair_exchange_to_std(msg['symbol'])

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

        await self.book_callback(self.l3_book[pair], L3_BOOK, pair,
                                 False, delta, timestamp_normalize(self.id, timestamp), timestamp)

    async def _handle_l3_msg(self, msg: str, timestamp: float):
        if msg['event'] == 'subscribed':
            LOG.info(f"Subscribed to {msg['symbol']}")
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
                            pair=msg['symbol'],
                            side=BUY if msg['side'] == 'buy' else SELL,
                            amount=msg['qty'],
                            price=msg['price'],
                            order_id=msg['trade_id'],
                            timestamp=timestamp_normalize(self.id, msg['timestamp']),
                            receipt_timestamp=timestamp)

    async def _handle_trade_msg(self, msg: str, timestamp: float):
        if msg['event'] == 'subscribed':
            LOG.info(f"Subscribed to trades for:  {msg['symbol']}")
        elif msg['event'] == 'updated':
            await self._trade(msg, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        if self.seq_no is not None and msg['seqnum'] != self.seq_no + 1:
            raise ValueError("Incorrect sequence number. TODO: implement ws restart")
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

    async def subscribe(self, websocket):
        self.__reset()
        if self.config:
            for channel in self.config:
                for pair in self.config[channel]:
                    await websocket.send(json.dumps({"action": "subscribe",
                                                     "symbol": pair,
                                                     "channel": channel
                                                     }))

        else:
            for pair, channel in product(self.pairs, self.channels):
                await websocket.send(json.dumps({"action": "subscribe",
                                                 "symbol": pair,
                                                 "channel": channel
                                                 }))

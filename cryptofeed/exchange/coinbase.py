'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from decimal import Decimal

import requests
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, COINBASE, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize, feed_to_exchange


LOG = logging.getLogger('feedhandler')


class Coinbase(Feed):
    id = COINBASE

    def __init__(self, callbacks=None, **kwargs):
        super().__init__('wss://ws-feed.pro.coinbase.com', callbacks=callbacks, **kwargs)
        # we only keep track of the L3 order book if we have at least one subscribed order-book callback.
        # use case: subscribing to the L3 book plus Trade type gives you order_type information (see _received below),
        # and we don't need to do the rest of the book-keeping unless we have an active callback
        self.keep_l3_book = False
        if callbacks and L3_BOOK in callbacks:
            self.keep_l3_book = True
        self.__reset()

    def __reset(self, symbol=None):
        if symbol:
            self.seq_no[symbol] = None
            self.order_map.pop(symbol, None)
            self.order_type_map.pop(symbol, None)
            self.l3_book.pop(symbol, None)
            self.l2_book.pop(symbol, None)
        else:
            self.order_map = {}
            self.order_type_map = {}
            self.seq_no = None
            # sequence number validation only works when the FULL data stream is enabled
            chan = feed_to_exchange(self.id, L3_BOOK)
            if chan in set(self.channels or self.subscription):
                pairs = set(self.symbols or self.subscription[chan])
                self.seq_no = {pair: None for pair in pairs}
            self.l3_book = {}
            self.l2_book = {}

    async def _ticker(self, msg: dict, timestamp: float):
        '''
        {
            'type': 'ticker',
            'sequence': 5928281084,
            'product_id': 'BTC-USD',
            'price': '8500.01000000',
            'open_24h': '8217.24000000',
            'volume_24h': '4529.1293778',
            'low_24h': '8172.00000000',
            'high_24h': '8600.00000000',
            'volume_30d': '329178.93594133',
            'best_bid': '8500',
            'best_ask': '8500.01'
        }

        {
            'type': 'ticker',
            'sequence': 5928281348,
            'product_id': 'BTC-USD',
            'price': '8500.00000000',
            'open_24h': '8217.24000000',
            'volume_24h': '4529.13179472',
            'low_24h': '8172.00000000',
            'high_24h': '8600.00000000',
            'volume_30d': '329178.93835825',
            'best_bid': '8500',
            'best_ask': '8500.01',
            'side': 'sell',
            'time': '2018-05-21T00:30:11.587000Z',
            'trade_id': 43736677,
            'last_size': '0.00241692'
        }
        '''
        await self.callback(TICKER, feed=self.id,
                            symbol=symbol_exchange_to_std(msg['product_id']),
                            bid=Decimal(msg['best_bid']),
                            ask=Decimal(msg['best_ask']),
                            timestamp=timestamp_normalize(self.id, msg['time']),
                            receipt_timestamp=timestamp)

    async def _book_update(self, msg: dict, timestamp: float):
        '''
        {
            'type': 'match', or last_match
            'trade_id': 43736593
            'maker_order_id': '2663b65f-b74e-4513-909d-975e3910cf22',
            'taker_order_id': 'd058d737-87f1-4763-bbb4-c2ccf2a40bde',
            'side': 'buy',
            'size': '0.01235647',
            'price': '8506.26000000',
            'product_id': 'BTC-USD',
            'sequence': 5928276661,
            'time': '2018-05-21T00:26:05.585000Z'
        }
        '''
        pair = symbol_exchange_to_std(msg['product_id'])
        ts = timestamp_normalize(self.id, msg['time'])

        if self.keep_l3_book and ('full' in self.channels or ('full' in self.subscription and pair in self.subscription['full'])):
            delta = {BID: [], ASK: []}
            price = Decimal(msg['price'])
            side = ASK if msg['side'] == 'sell' else BID
            size = Decimal(msg['size'])
            maker_order_id = msg['maker_order_id']

            _, new_size = self.order_map[maker_order_id]
            new_size -= size
            if new_size <= 0:
                del self.order_map[maker_order_id]
                self.order_type_map.pop(maker_order_id, None)
                delta[side].append((maker_order_id, price, 0))
                del self.l3_book[pair][side][price][maker_order_id]
                if len(self.l3_book[pair][side][price]) == 0:
                    del self.l3_book[pair][side][price]
            else:
                self.order_map[maker_order_id] = (price, new_size)
                self.l3_book[pair][side][price][maker_order_id] = new_size
                delta[side].append((maker_order_id, price, new_size))

            await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, ts, timestamp)

        order_type = self.order_type_map.get(msg['taker_order_id'])
        await self.callback(TRADES,
                            feed=self.id,
                            symbol=symbol_exchange_to_std(msg['product_id']),
                            order_id=msg['trade_id'],
                            side=SELL if msg['side'] == 'buy' else BUY,
                            amount=Decimal(msg['size']),
                            price=Decimal(msg['price']),
                            timestamp=ts,
                            receipt_timestamp=timestamp,
                            order_type=order_type
                            )

    async def _pair_level2_snapshot(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['product_id'])
        self.l2_book[pair] = {
            BID: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['bids']
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for price, amount in msg['asks']
            })
        }

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp, timestamp)

    async def _pair_level2_update(self, msg: dict, timestamp: float):
        pair = symbol_exchange_to_std(msg['product_id'])
        ts = timestamp_normalize(self.id, msg['time'])
        delta = {BID: [], ASK: []}
        for side, price, amount in msg['changes']:
            side = BID if side == 'buy' else ASK
            price = Decimal(price)
            amount = Decimal(amount)
            bidask = self.l2_book[pair][side]

            if amount == 0:
                del bidask[price]
                delta[side].append((price, 0))
            else:
                bidask[price] = amount
                delta[side].append((price, amount))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, ts, timestamp)

    async def _book_snapshot(self, pairs: list):
        # Coinbase needs some time to send messages to us
        # before we request the snapshot. If we don't sleep
        # the snapshot seq no could be much earlier than
        # the subsequent messages, causing a seq no mismatch.
        await asyncio.sleep(2)

        url = 'https://api.pro.coinbase.com/products/{}/book?level=3'
        urls = [url.format(pair) for pair in pairs]

        results = []
        for url in urls:
            ret = requests.get(url)
            results.append(ret)
            # rate limit - 3 per second
            await asyncio.sleep(0.3)

        timestamp = time.time()
        for res, pair in zip(results, pairs):
            orders = res.json()
            npair = symbol_exchange_to_std(pair)
            self.l3_book[npair] = {BID: sd(), ASK: sd()}
            self.seq_no[npair] = orders['sequence']
            for side in (BID, ASK):
                for price, size, order_id in orders[side + 's']:
                    price = Decimal(price)
                    size = Decimal(size)
                    if price in self.l3_book[npair][side]:
                        self.l3_book[npair][side][price][order_id] = size
                    else:
                        self.l3_book[npair][side][price] = {order_id: size}
                    self.order_map[order_id] = (price, size)
            await self.book_callback(self.l3_book[npair], L3_BOOK, npair, True, None, timestamp, timestamp)

    async def _open(self, msg: dict, timestamp: float):
        if not self.keep_l3_book:
            return
        delta = {BID: [], ASK: []}
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        size = Decimal(msg['remaining_size'])
        pair = symbol_exchange_to_std(msg['product_id'])
        order_id = msg['order_id']
        ts = timestamp_normalize(self.id, msg['time'])

        if price in self.l3_book[pair][side]:
            self.l3_book[pair][side][price][order_id] = size
        else:
            self.l3_book[pair][side][price] = {order_id: size}
        self.order_map[order_id] = (price, size)

        delta[side].append((order_id, price, size))

        await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, ts, timestamp)

    async def _done(self, msg: dict, timestamp: float):
        """
        per Coinbase API Docs:

        A done message will be sent for received orders which are fully filled or canceled due
        to self-trade prevention. There will be no open message for such orders. Done messages
        for orders which are not on the book should be ignored when maintaining a real-time order book.
        """
        if 'price' not in msg:
            return

        order_id = msg['order_id']
        self.order_type_map.pop(order_id, None)
        if order_id not in self.order_map:
            return

        del self.order_map[order_id]
        if self.keep_l3_book:
            delta = {BID: [], ASK: []}

            price = Decimal(msg['price'])
            side = ASK if msg['side'] == 'sell' else BID
            pair = symbol_exchange_to_std(msg['product_id'])
            ts = timestamp_normalize(self.id, msg['time'])

            del self.l3_book[pair][side][price][order_id]
            if len(self.l3_book[pair][side][price]) == 0:
                del self.l3_book[pair][side][price]
            delta[side].append((order_id, price, 0))

            await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, delta, ts, timestamp)

    async def _received(self, msg: dict, timestamp: float):
        """
        per Coinbase docs:
        A valid order has been received and is now active. This message is emitted for every single
        valid order as soon as the matching engine receives it whether it fills immediately or not.

        This message is the only time we receive the order type (limit vs market) for a given order,
        so we keep it in a map by order ID.
        """
        order_id = msg["order_id"]
        order_type = msg["order_type"]
        self.order_type_map[order_id] = order_type

    async def _change(self, msg: dict, timestamp: float):
        """
        Like done, these updates can be sent for orders that are not in the book. Per the docs:

        Not all done or change messages will result in changing the order book. These messages will
        be sent for received orders which are not yet on the order book. Do not alter
        the order book for such messages, otherwise your order book will be incorrect.
        """
        if not self.keep_l3_book:
            return

        delta = {BID: [], ASK: []}

        if 'price' not in msg or not msg['price']:
            return

        order_id = msg['order_id']
        if order_id not in self.order_map:
            return

        ts = timestamp_normalize(self.id, msg['time'])
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        new_size = Decimal(msg['new_size'])
        pair = symbol_exchange_to_std(msg['product_id'])

        self.l3_book[pair][side][price][order_id] = new_size
        self.order_map[order_id] = (price, new_size)

        delta[side].append((order_id, price, new_size))

        await self.book_callback(self.l3_book, L3_BOOK, pair, False, delta, ts, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        # PERF perf_start(self.id, 'msg')
        msg = json.loads(msg, parse_float=Decimal)
        if self.seq_no:
            if 'product_id' in msg and 'sequence' in msg:
                pair = symbol_exchange_to_std(msg['product_id'])
                if not self.seq_no.get(pair, None):
                    return
                if msg['sequence'] <= self.seq_no[pair]:
                    return
                if msg['sequence'] != self.seq_no[pair] + 1:
                    LOG.warning("%s: Missing sequence number detected for %s. Received %d, expected %d", self.id, pair, msg['sequence'], self.seq_no[pair] + 1)
                    LOG.warning("%s: Resetting data for %s", self.id, pair)
                    self.__reset(symbol=pair)
                    await self._book_snapshot([pair])
                    return

                self.seq_no[pair] = msg['sequence']

        if 'type' in msg:
            if msg['type'] == 'ticker':
                await self._ticker(msg, timestamp)
            elif msg['type'] == 'match' or msg['type'] == 'last_match':
                await self._book_update(msg, timestamp)
            elif msg['type'] == 'snapshot':
                await self._pair_level2_snapshot(msg, timestamp)
            elif msg['type'] == 'l2update':
                await self._pair_level2_update(msg, timestamp)
            elif msg['type'] == 'open':
                await self._open(msg, timestamp)
            elif msg['type'] == 'done':
                await self._done(msg, timestamp)
            elif msg['type'] == 'change':
                await self._change(msg, timestamp)
            elif msg['type'] == 'received':
                await self._received(msg, timestamp)
            elif msg['type'] == 'activate':
                pass
            elif msg['type'] == 'subscriptions':
                pass
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
            # PERF perf_end(self.id, 'msg')
            # PERF perf_log(self.id, 'msg')

    async def subscribe(self, conn: AsyncConnection, symbol=None):
        self.__reset(symbol=symbol)

        for chan in set(self.channels or self.subscription):
            await conn.send(json.dumps({"type": "subscribe",
                                        "product_ids": list(self.symbols or self.subscription[chan]),
                                        "channels": [chan]
                                        }))

        chan = feed_to_exchange(self.id, L3_BOOK)
        if chan in set(self.channels or self.subscription):
            await self._book_snapshot(list(self.symbols or self.subscription[chan]))

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, COINBASE, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.coinbase_rest import CoinbaseRestMixin
from cryptofeed.types import OrderBook, Ticker, Trade


LOG = logging.getLogger('feedhandler')


class Coinbase(Feed, CoinbaseRestMixin):
    id = COINBASE
    symbol_endpoint = 'https://api.pro.coinbase.com/products'
    websocket_channels = {
        L2_BOOK: 'level2',
        L3_BOOK: 'full',
        TRADES: 'matches',
        TICKER: 'ticker',
    }
    request_limit = 10

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            sym = Symbol(entry['base_currency'], entry['quote_currency'])
            info['tick_size'][sym.normalized] = entry['quote_increment']
            info['instrument_type'][sym.normalized] = sym.type
            ret[sym.normalized] = entry['id']
        return ret, info

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
            self._l3_book.pop(symbol, None)
            self._l2_book.pop(symbol, None)
        else:
            self.order_map = {}
            self.order_type_map = {}
            self.seq_no = None
            # sequence number validation only works when the FULL data stream is enabled
            chan = self.std_channel_to_exchange(L3_BOOK)
            if chan in self.subscription:
                pairs = self.subscription[chan]
                self.seq_no = {pair: None for pair in pairs}
            self._l3_book = {}
            self._l2_book = {}

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
        await self.callback(TICKER, Ticker(self.id, self.exchange_symbol_to_std_symbol(msg['product_id']), Decimal(msg['best_bid']), Decimal(msg['best_ask']), self.timestamp_normalize(msg['time']), raw=msg), timestamp)

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
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        ts = self.timestamp_normalize(msg['time'])

        if self.keep_l3_book and 'full' in self.subscription and pair in self.subscription['full']:
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
                del self._l3_book[pair].book[side][price][maker_order_id]
                if len(self._l3_book[pair].book[side][price]) == 0:
                    del self._l3_book[pair].book[side][price]
            else:
                self.order_map[maker_order_id] = (price, new_size)
                self._l3_book[pair].book[side][price][maker_order_id] = new_size
                delta[side].append((maker_order_id, price, new_size))

            await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, timestamp=ts, delta=delta, raw=msg, sequence_number=self.seq_no[pair])

        order_type = self.order_type_map.get(msg['taker_order_id'])
        t = Trade(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['product_id']),
            SELL if msg['side'] == 'buy' else BUY,
            Decimal(msg['size']),
            Decimal(msg['price']),
            ts,
            id=str(msg['trade_id']),
            type=order_type,
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def _pair_level2_snapshot(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        bids = {Decimal(price): Decimal(amount) for price, amount in msg['bids']}
        asks = {Decimal(price): Decimal(amount) for price, amount in msg['asks']}
        if pair not in self._l2_book:
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks)
        else:
            self._l2_book[pair].book.bids = bids
            self._l2_book[pair].book.asks = asks

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg)

    async def _pair_level2_update(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        ts = self.timestamp_normalize(msg['time'])
        delta = {BID: [], ASK: []}
        for side, price, amount in msg['changes']:
            side = BID if side == 'buy' else ASK
            price = Decimal(price)
            amount = Decimal(amount)

            if amount == 0:
                del self._l2_book[pair].book[side][price]
                delta[side].append((price, 0))
            else:
                self._l2_book[pair].book[side][price] = amount
                delta[side].append((price, amount))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=ts, raw=msg, delta=delta)

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
            ret = await self.http_conn.read(url)
            results.append(ret)
            # rate limit - 3 per second
            await asyncio.sleep(0.3)

        timestamp = time.time()
        for res, pair in zip(results, pairs):
            orders = json.loads(res, parse_float=Decimal)
            npair = self.exchange_symbol_to_std_symbol(pair)
            self._l3_book[npair] = OrderBook(self.id, pair, max_depth=self.max_depth)
            self.seq_no[npair] = orders['sequence']
            for side in (BID, ASK):
                for price, size, order_id in orders[side + 's']:
                    price = Decimal(price)
                    size = Decimal(size)
                    if price in self._l3_book[npair].book[side]:
                        self._l3_book[npair].book[side][price][order_id] = size
                    else:
                        self._l3_book[npair].book[side][price] = {order_id: size}
                    self.order_map[order_id] = (price, size)
            await self.book_callback(L3_BOOK, self._l3_book[npair], timestamp, raw=orders)

    async def _open(self, msg: dict, timestamp: float):
        if not self.keep_l3_book:
            return
        delta = {BID: [], ASK: []}
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        size = Decimal(msg['remaining_size'])
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        order_id = msg['order_id']
        ts = self.timestamp_normalize(msg['time'])

        if price in self._l3_book[pair].book[side]:
            self._l3_book[pair].book[side][price][order_id] = size
        else:
            self._l3_book[pair].book[side][price] = {order_id: size}
        self.order_map[order_id] = (price, size)

        delta[side].append((order_id, price, size))

        await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, timestamp=ts, delta=delta, raw=msg, sequence_number=msg['sequence'])

    async def _done(self, msg: dict, timestamp: float):
        """
        per Coinbase API Docs:

        A done message will be sent for received orders which are fully filled or canceled due
        to self-trade prevention. There will be no open message for such orders. Done messages
        for orders which are not on the book should be ignored when maintaining a real-time order book.
        """
        if 'price' not in msg:
            # market order life cycle: received -> done
            self.order_type_map.pop(msg['order_id'], None)
            self.order_map.pop(msg['order_id'], None)
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
            pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
            ts = self.timestamp_normalize(msg['time'])

            del self._l3_book[pair].book[side][price][order_id]
            if len(self._l3_book[pair].book[side][price]) == 0:
                del self._l3_book[pair].book[side][price]
            delta[side].append((order_id, price, 0))

            await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, delta=delta, timestamp=ts, raw=msg, sequence_number=msg['sequence'])

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

        ts = self.timestamp_normalize(msg['time'])
        price = Decimal(msg['price'])
        side = ASK if msg['side'] == 'sell' else BID
        new_size = Decimal(msg['new_size'])
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])

        self._l3_book[pair].book[side][price][order_id] = new_size
        self.order_map[order_id] = (price, new_size)

        delta[side].append((order_id, price, new_size))

        await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, delta=delta, timestamp=ts, raw=msg, sequence_number=msg['sequence'])

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        # PERF perf_start(self.id, 'msg')
        msg = json.loads(msg, parse_float=Decimal)
        if self.seq_no:
            if 'product_id' in msg and 'sequence' in msg:
                pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
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

        for chan in self.subscription:
            await conn.write(json.dumps({"type": "subscribe",
                                         "product_ids": self.subscription[chan],
                                         "channels": [chan]
                                         }))

        chan = self.std_channel_to_exchange(L3_BOOK)
        if chan in self.subscription:
            await self._book_snapshot(self.subscription[chan])

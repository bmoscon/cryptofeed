'''
Copyright (C) 2017-2024 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import hashlib
import hmac
import logging
import time
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, COINBASE, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES, CANDLES, ORDERS
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.coinbase_rest import CoinbaseRestMixin
from cryptofeed.types import OrderBook, Ticker, Trade

LOG = logging.getLogger('feedhandler')


class Coinbase(Feed, CoinbaseRestMixin):
    id = COINBASE
    websocket_endpoints = [WebsocketEndpoint('wss://advanced-trade-ws.coinbase.com', options={'compression': None})]
    rest_endpoints = [
        RestEndpoint('https://api.pro.coinbase.com', routes=Routes('/products', l3book='/products/{}/book?level=3'))]

    # TODO: implement candles and user channels
    websocket_channels = {
        L2_BOOK: 'level2',
        TRADES: 'market_trades',
    }
    request_limit = 10

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            base, quote = entry['id'].split("-")
            sym = Symbol(base, quote)
            info['tick_size'][sym.normalized] = entry['quote_increment']
            info['instrument_type'][sym.normalized] = sym.type
            ret[sym.normalized] = entry['id']
        return ret, info

    def __init__(self, callbacks=None, **kwargs):
        super().__init__(callbacks=callbacks, **kwargs)
        # we only keep track of the L3 order book if we have at least one subscribed order-book callback.
        # use case: subscribing to the L3 book plus Trade type gives you order_type information (see _received below),
        # and we don't need to do the rest of the book-keeping unless we have an active callback
        self.__reset()

    def __reset(self):
        self.order_map = {}
        self.order_type_map = {}
        self.seq_no = None
        self._l2_book = {}

    async def _ticker(self, msg: dict, timestamp: float):
        # TODO: The ticker endpoint payload has been updated and no longer includes best ask and bid.
        #  Do we want to:
        #  1. get rid of that callback
        #  2. implement ticker based on l2 book sub
        #  3. implement a new ticker callback (will be different from other exchanges)
        raise NotImplementedError

    async def _trade_update(self, msg: dict, timestamp: float):
        '''
        {
            'trade_id': 43736593
            'side': 'BUY' or 'SELL',
            'size': '0.01235647',
            'price': '8506.26000000',
            'product_id': 'BTC-USD',
            'time': '2018-05-21T00:26:05.585000Z'
        }
        '''
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        ts = self.timestamp_normalize(msg['time'])
        order_type = 'market'
        t = Trade(
            self.id,
            pair,
            SELL if msg['side'] == 'SELL' else BUY,
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
        bids = {Decimal(update['price_level']): Decimal(update['new_quantity']) for update in msg['updates'] if
                update['side'] == 'bid'}
        asks = {Decimal(update['price_level']): Decimal(update['new_quantity']) for update in msg['updates'] if
                update['side'] == 'ask'}
        if pair not in self._l2_book:
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks)
        else:
            self._l2_book[pair].book.bids = bids
            self._l2_book[pair].book.asks = asks

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg)

    async def _pair_level2_update(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['product_id'])
        delta = {BID: [], ASK: []}
        for update in msg['updates']:
            ts = self.timestamp_normalize(update['event_time'])
            side = BID if update['side'] == 'bid' else ASK
            price = Decimal(update['price_level'])
            amount = Decimal(update['new_quantity'])

            if amount == 0:
                if price in self._l2_book[pair].book[side]:
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

        # TODO: not yet updated
        urls = [self.rest_endpoints[0].route('l3book', self.sandbox).format(pair) for pair in pairs]

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

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        # PERF perf_start(self.id, 'msg')
        msg = json.loads(msg, parse_float=Decimal)
        if 'channel' in msg and 'events' in msg:
            for event in msg['events']:
                if self.seq_no and 'product_id' in event and 'sequence_num' in msg:
                    pair = self.exchange_symbol_to_std_symbol(event['product_id'])
                    if not self.seq_no.get(pair, None):
                        return
                    if msg['sequence_num'] <= self.seq_no[pair]:
                        return
                    if msg['sequence_num'] != self.seq_no[pair] + 1:
                        LOG.warning("%s: Missing sequence number detected for %s. Received %d, expected %d", self.id,
                                    pair, msg['sequence_num'], self.seq_no[pair] + 1)
                        LOG.warning("%s: Resetting data for %s", self.id, pair)
                        self.__reset()
                        await self._book_snapshot([pair])
                        return

                    self.seq_no[pair] = msg['sequence_num']

                if msg['channel'] == 'market_trades':
                    if event.get('type') == 'update':
                        for trade in event['trades']:
                            await self._trade_update(trade, timestamp)
                    else:
                        pass  # TODO: do we want to implement trades snapshots?
                elif msg['channel'] == 'l2_data':
                    if event.get('type') == 'update':
                        await self._pair_level2_update(event, timestamp)
                    elif event.get('type') == 'snapshot':
                        await self._pair_level2_snapshot(event, timestamp)
                elif msg['channel'] == 'subscriptions':
                    pass
                else:
                    LOG.warning("%s: Invalid message type %s", self.id, msg)
                # PERF perf_end(self.id, 'msg')
                # PERF perf_log(self.id, 'msg')

    async def get_private_parameters(self, chan: str, product_ids_str: list) -> dict:
        timestamp = str(int(time.time()))
        product_ids_str = ",".join(product_ids_str)
        message = f"{timestamp}{chan}{product_ids_str}"
        signature = hmac.new(
            self.config["coinbase"]["key_secret"].encode("utf-8"),
            message.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return dict(api_key=self.config["coinbase"]["key_id"], timestamp=timestamp, signature=signature)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        all_pairs = list()

        async def _subscribe(chan: str, product_ids: list):
            params = {"type": "subscribe",
                      "product_ids": product_ids,
                      "channel": chan
                      }
            private_params = await self.get_private_parameters(chan, product_ids)
            if private_params:
                params = {**params, **private_params}
            await conn.write(json.dumps(params))

        for channel in self.subscription:
            all_pairs += self.subscription[channel]
            await _subscribe(channel, self.subscription[channel])
        all_pairs = list(dict.fromkeys(all_pairs))
        await _subscribe('heartbeat', all_pairs)
        # Implementing heartbase as per Best Practices doc: https://docs.cloud.coinbase.com/advanced-trade-api/docs/ws-best-practices

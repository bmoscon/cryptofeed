'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple
import time

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BITSTAMP, BUY, L2_BOOK, L3_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.exchanges.mixins.bitstamp_rest import BitstampRestMixin
from cryptofeed.types import OrderBook, Trade


LOG = logging.getLogger('feedhandler')


class Bitstamp(Feed, BitstampRestMixin):
    id = BITSTAMP
    symbol_endpoint = "https://www.bitstamp.net/api/v2/trading-pairs-info/"
    # API documentation: https://www.bitstamp.net/websocket/v2/
    websocket_channels = {
        L3_BOOK: 'detail_order_book',
        L2_BOOK: 'diff_order_book',
        TRADES: 'live_trades',
    }
    request_limit = 13

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1_000_000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}

        for d in data:
            if d['trading'] != 'Enabled':
                continue
            base, quote = d['name'].split("/")
            s = Symbol(base, quote)
            symbol = d['url_symbol']
            ret[s.normalized] = symbol
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://ws.bitstamp.net/', **kwargs)

    async def _process_l2_book(self, msg: dict, timestamp: float):
        data = msg['data']
        chan = msg['channel']
        ts = int(data['microtimestamp'])
        pair = self.exchange_symbol_to_std_symbol(chan.split('_')[-1])
        delta = {BID: [], ASK: []}

        if pair in self.last_update_id:
            if data['timestamp'] < self.last_update_id[pair]:
                return
            else:
                del self.last_update_id[pair]

        for side in (BID, ASK):
            for update in data[side + 's']:
                price = Decimal(update[0])
                size = Decimal(update[1])

                if size == 0:
                    if price in self._l2_book[pair].book[side]:
                        del self._l2_book[pair].book[side][price]
                        delta[side].append((price, size))
                else:
                    self._l2_book[pair].book[side][price] = size
                    delta[side].append((price, size))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(ts), delta=delta, raw=msg)

    async def _process_l3_book(self, msg: dict, timestamp: float):
        data = msg['data']
        chan = msg['channel']
        ts = int(data['microtimestamp'])
        pair = self.exchange_symbol_to_std_symbol(chan.split('_')[-1])

        book = OrderBook(self.id, pair, max_depth=self.max_depth)
        for side in (BID, ASK):
            for price, size, order_id in data[side + 's']:
                price = Decimal(price)
                size = Decimal(size)
                if price in book.book[side]:
                    book.book[side][price][order_id] = size
                else:
                    book.book[side][price] = {order_id: size}

        self._l3_book[pair] = book
        await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, timestamp=self.timestamp_normalize(ts), raw=msg)

    async def _trades(self, msg: dict, timestamp: float):
        """
        {'data':
         {
         'microtimestamp': '1562650233964229',      // Event time (micros)
         'amount': Decimal('0.014140160000000001'), // Quantity
         'buy_order_id': 3709484695,                // Buyer order ID
         'sell_order_id': 3709484799,               // Seller order ID
         'amount_str': '0.01414016',                // Quantity string
         'price_str': '12700.00',                   // Price string
         'timestamp': '1562650233',                 // Event time
         'price': Decimal('12700.0'),               // Price
         'type': 1,
         'id': 93215787
         },
         'event': 'trade',
         'channel': 'live_trades_btcusd'
        }
        """
        data = msg['data']
        chan = msg['channel']
        pair = self.exchange_symbol_to_std_symbol(chan.split('_')[-1])

        t = Trade(
            self.id,
            pair,
            BUY if data['type'] == 0 else SELL,
            Decimal(data['amount']),
            Decimal(data['price']),
            self.timestamp_normalize(int(data['microtimestamp'])),
            id=str(data['id']),
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)
        if 'bts' in msg['event']:
            if msg['event'] == 'bts:connection_established':
                pass
            elif msg['event'] == 'bts:subscription_succeeded':
                pass
            else:
                LOG.warning("%s: Unexpected message %s", self.id, msg)
        elif msg['event'] == 'trade':
            await self._trades(msg, timestamp)
        elif msg['event'] == 'data':
            if msg['channel'].startswith('diff_order_book'):
                await self._process_l2_book(msg, timestamp)
            if msg['channel'].startswith('detail_order_book'):
                await self._process_l3_book(msg, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def _snapshot(self, pairs: list, conn: AsyncConnection):
        await asyncio.sleep(5)
        urls = [f'https://www.bitstamp.net/api/v2/order_book/{sym}' for sym in pairs]
        results = [await self.http_conn.read(url) for url in urls]
        results = [json.loads(resp, parse_float=Decimal) for resp in results]

        for r, pair in zip(results, pairs):
            std_pair = self.exchange_symbol_to_std_symbol(pair) if pair else 'BTC-USD'
            self.last_update_id[std_pair] = r['timestamp']
            self._l2_book[std_pair] = OrderBook(self.id, std_pair, max_depth=self.max_depth, asks={Decimal(u[0]): Decimal(u[1]) for u in r['asks']}, bids={Decimal(u[0]): Decimal(u[1]) for u in r['bids']})
            await self.book_callback(L2_BOOK, self._l2_book[std_pair], time.time(), timestamp=float(r['timestamp']), raw=r)

    async def subscribe(self, conn: AsyncConnection):
        snaps = []
        self.last_update_id = {}
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                await conn.write(
                    json.dumps({
                        "event": "bts:subscribe",
                        "data": {
                            "channel": f"{chan}_{pair}"
                        }
                    }))
                if 'diff_order_book' in chan:
                    snaps.append(pair)
        await self._snapshot(snaps, conn)

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from decimal import Decimal

import aiohttp
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BITSTAMP, BUY, L2_BOOK, L3_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import feed_to_exchange, symbol_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Bitstamp(Feed):
    id = BITSTAMP
    # API documentation: https://www.bitstamp.net/websocket/v2/

    def __init__(self, **kwargs):
        super().__init__('wss://ws.bitstamp.net/', **kwargs)

    async def _l2_book(self, msg: dict, timestamp: float):
        data = msg['data']
        chan = msg['channel']
        ts = int(data['microtimestamp'])
        pair = symbol_exchange_to_std(chan.split('_')[-1])
        forced = False
        delta = {BID: [], ASK: []}

        if pair in self.last_update_id:
            if data['timestamp'] < self.last_update_id[pair]:
                return
            else:
                forced = True
                del self.last_update_id[pair]

        for side in (BID, ASK):
            for update in data[side + 's']:
                price = Decimal(update[0])
                size = Decimal(update[1])

                if size == 0:
                    if price in self.l2_book[pair][side]:
                        del self.l2_book[pair][side][price]
                        delta[side].append((price, size))
                else:
                    self.l2_book[pair][side][price] = size
                    delta[side].append((price, size))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp_normalize(self.id, ts), timestamp)

    async def _l3_book(self, msg: dict, timestamp: float):
        data = msg['data']
        chan = msg['channel']
        ts = int(data['microtimestamp'])
        pair = symbol_exchange_to_std(chan.split('_')[-1])

        book = {BID: sd(), ASK: sd()}
        for side in (BID, ASK):
            for price, size, order_id in data[side + 's']:
                price = Decimal(price)
                size = Decimal(size)
                book[side].get(price, sd())[order_id] = size
        self.l3_book[pair] = book
        await self.book_callback(self.l3_book[pair], L3_BOOK, pair, False, False, timestamp_normalize(self.id, ts), timestamp)

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
        pair = symbol_exchange_to_std(chan.split('_')[-1])

        side = BUY if data['type'] == 0 else SELL
        amount = Decimal(data['amount'])
        price = Decimal(data['price'])
        ts = int(data['microtimestamp'])
        order_id = data['id']
        await self.callback(TRADES, feed=self.id,
                            symbol=pair,
                            side=side,
                            amount=amount,
                            price=price,
                            timestamp=timestamp_normalize(self.id, ts),
                            receipt_timestamp=timestamp,
                            order_id=order_id)

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
            if msg['channel'].startswith(feed_to_exchange(self.id, L2_BOOK)):
                await self._l2_book(msg, timestamp)
            if msg['channel'].startswith(feed_to_exchange(self.id, L3_BOOK)):
                await self._l3_book(msg, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def _snapshot(self, pairs: list):
        await asyncio.sleep(5)
        urls = [f'https://www.bitstamp.net/api/v2/order_book/{sym}' for sym in pairs]

        async def fetch(session, url):
            async with session.get(url) as response:
                response.raise_for_status()
                return await response.json()

        async with aiohttp.ClientSession() as session:
            results = await asyncio.gather(*[fetch(session, url) for url in urls])

        for r, pair in zip(results, pairs):
            std_pair = symbol_exchange_to_std(pair) if pair else 'BTC-USD'
            self.last_update_id[std_pair] = r['timestamp']
            self.l2_book[std_pair] = {BID: sd(), ASK: sd()}
            for s, side in (('bids', BID), ('asks', ASK)):
                for update in r[s]:
                    price = Decimal(update[0])
                    amount = Decimal(update[1])
                    self.l2_book[std_pair][side][price] = amount

    async def subscribe(self, conn: AsyncConnection):
        snaps = []
        self.last_update_id = {}
        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                await conn.send(
                    json.dumps({
                        "event": "bts:subscribe",
                        "data": {
                            "channel": f"{chan}_{pair}"
                        }
                    }))
                if 'diff_order_book' in chan:
                    snaps.append(pair)
        await self._snapshot(snaps)

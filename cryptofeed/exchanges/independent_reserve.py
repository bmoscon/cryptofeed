'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
from typing import Dict, Tuple
from collections import defaultdict
from time import time

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, BUY, ASK, INDEPENDENT_RESERVE, L3_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.types import Trade, OrderBook


LOG = logging.getLogger('feedhandler')


class IndependentReserve(Feed):
    id = INDEPENDENT_RESERVE
    websocket_endpoints = [WebsocketEndpoint('wss://websockets.independentreserve.com')]
    rest_endpoints = [RestEndpoint('https://api.independentreserve.com', routes=Routes(['/Public/GetValidPrimaryCurrencyCodes', '/Public/GetValidSecondaryCurrencyCodes'], l3book='/Public/GetAllOrders?primaryCurrencyCode={}&secondaryCurrencyCode={}'))]

    websocket_channels = {
        L3_BOOK: 'orderbook-{}',
        TRADES: 'ticker-{}',
    }
    request_limit = 1

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        bases, quotes = data
        for base in bases:
            for quote in quotes:
                sym = Symbol(base.upper().replace('XBT', 'BTC'), quote.upper())
                info['instrument_type'][sym.normalized] = sym.type
                ret[sym.normalized] = f"{base.lower()}-{quote.lower()}"
        return ret, info

    def __reset(self):
        self._l3_book = {}
        self._order_ids = defaultdict(dict)
        self._sequence_no = {}

    async def _trade(self, msg: dict, timestamp: float):
        '''
        {
            'Channel': 'ticker-eth-aud',
            'Nonce': 78,
            'Data': {
                'TradeGuid': '6d1c2e90-592a-409c-a8d8-58b2d25e0b0b',
                'Pair': 'eth-aud',
                'TradeDate': datetime.datetime(2022, 1, 31, 8, 28, 26, 552573, tzinfo=datetime.timezone(datetime.timedelta(seconds=39600))),
                'Price': Decimal('3650.81'),
                'Volume': Decimal('0.543'),
                'BidGuid': '0430e003-c35e-410e-85f5-f0bb5c40193b',
                'OfferGuid': '559c1dd2-e681-4efc-b49b-14a07c069de4',
                'Side': 'Sell'
            },
            'Time': 1643578106584,
            'Event': 'Trade'
        }
        '''
        t = Trade(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['Data']['Pair']),
            SELL if msg['Data']['Side'] == 'Sell' else BUY,
            Decimal(msg['Data']['Volume']),
            Decimal(msg['Data']['Price']),
            self.timestamp_normalize(msg['Data']['TradeDate']),
            id=msg['Data']['TradeGuid'],
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        '''
        {
            'Channel': 'orderbook-xbt',
            'Nonce': 65605,
            'Data': {
                'OrderType': 'LimitBid',
                'OrderGuid': 'fee7094c-1921-44b7-8d8d-8b6e1cedb270'
            },
            'Time': 1643931382903,
            'Event': 'OrderCanceled'
        }

        {
            'Channel': 'orderbook-xbt',
            'Nonce': 65606,
            'Data': {
                'OrderType': 'LimitOffer',
                'OrderGuid': '22a72137-9829-4e6c-b265-a38714256877',
                'Price': {
                    'aud': Decimal('51833.41'),
                    'usd': Decimal('37191.23'),
                    'nzd': Decimal('55836.92'),
                    'sgd': Decimal('49892.59')
                },
                'Volume': Decimal('0.09')
            },
            'Time': 1643931382903,
            'Event': 'NewOrder'
        }
        '''
        seq_no = msg['Nonce']
        base = msg['Channel'].split('-')[-1]
        delta = {BID: [], ASK: []}

        for symbol in self.subscription[self.std_channel_to_exchange(L3_BOOK)]:
            if symbol.startswith(base):
                quote = symbol.split('-')[-1]
                instrument = self.exchange_symbol_to_std_symbol(f"{base}-{quote}")
                if instrument in self._sequence_no and self._sequence_no[instrument] + 1 != seq_no:
                    raise MissingSequenceNumber
                self._sequence_no[instrument] = seq_no

                if instrument not in self._l3_book:
                    await self._snapshot(base, quote)

                if msg['Event'] == 'OrderCanceled':
                    uuid = msg['Data']['OrderGuid']
                    if uuid in self._order_ids[instrument]:
                        price, side = self._order_ids[instrument][uuid]

                        if price in self._l3_book[instrument].book[side] and uuid in self._l3_book[instrument].book[side][price]:
                            del self._l3_book[instrument].book[side][price][uuid]
                            if len(self._l3_book[instrument].book[side][price]) == 0:
                                del self._l3_book[instrument].book[side][price]
                            delta[side].append((uuid, price, 0))

                        del self._order_ids[instrument][uuid]
                    else:
                        # during snapshots we might get cancelation messages that have already been removed
                        # from the snapshot, so we don't have anything to process, and we should not call the client callback
                        continue
                elif msg['Event'] == 'NewOrder':
                    uuid = msg['Data']['OrderGuid']
                    price = msg['Data']['Price'][quote]
                    size = msg['Data']['Volume']
                    side = BID if msg['Data']['OrderType'].endswith('Bid') else ASK
                    self._order_ids[instrument][uuid] = (price, side)

                    if price in self._l3_book[instrument].book[side]:
                        self._l3_book[instrument].book[side][price][uuid] = size
                    else:
                        self._l3_book[instrument].book[side][price] = {uuid: size}
                    delta[side].append((uuid, price, size))

                elif msg['Event'] == 'OrderChanged':
                    uuid = msg['Data']['OrderGuid']
                    size = msg['Data']['Volume']
                    side = BID if msg['Data']['OrderType'].endswith('Bid') else ASK
                    if uuid in self._order_ids[instrument]:
                        price, side = self._order_ids[instrument][uuid]

                        if size == 0:
                            del self._l3_book[instrument].book[side][price][uuid]
                            if len(self._l3_book[instrument].book[side][price]) == 0:
                                del self._l3_book[instrument].book[side][price]
                        else:
                            self._l3_book[instrument].book[side][price][uuid] = size

                        del self._order_ids[instrument][uuid]
                        delta[side].append((uuid, price, size))
                    else:
                        continue

                else:
                    raise ValueError("%s: Invalid OrderBook event message of type %s", self.id, msg)

                await self.book_callback(L3_BOOK, self._l3_book[instrument], timestamp, raw=msg, sequence_number=seq_no, delta=delta, timestamp=msg['Time'] / 1000)

    async def _snapshot(self, base: str, quote: str):
        url = self.rest_endpoints[0].route('l3book', self.sandbox).format(base, quote)
        timestamp = time()
        ret = await self.http_conn.read(url)
        await asyncio.sleep(1 / self.request_limit)
        ret = json.loads(ret, parse_float=Decimal)

        normalized = self.exchange_symbol_to_std_symbol(f"{base}-{quote}")
        self._l3_book[normalized] = OrderBook(self.id, normalized, max_depth=self.max_depth)

        for side, key in [(BID, 'BuyOrders'), (ASK, 'SellOrders')]:
            for order in ret[key]:
                price = Decimal(order['Price'])
                size = Decimal(order['Volume'])
                uuid = order['Guid']
                self._order_ids[normalized][uuid] = (price, side)

                if price in self._l3_book[normalized].book[side]:
                    self._l3_book[normalized].book[side][price][uuid] = size
                else:
                    self._l3_book[normalized].book[side][price] = {uuid: size}
        await self.book_callback(L3_BOOK, self._l3_book[normalized], timestamp, raw=ret)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['Event'] == 'Trade':
            await self._trade(msg, timestamp)
        elif msg['Event'] in ('OrderCanceled', 'OrderChanged', 'NewOrder'):
            await self._book(msg, timestamp)
        elif msg['Event'] in ('Subscriptions', 'Heartbeat', 'Unsubscribe'):
            return
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        subs = []
        for chan, symbols in conn.subscription.items():
            if self.exchange_channel_to_std(chan) == L3_BOOK:
                subs.extend([chan.format(s) for s in set([sym.split("-")[0] for sym in symbols])])
            else:
                subs.extend([chan.format(s) for s in symbols])

        await conn.write(json.dumps({"Event": "Subscribe", "Data": subs}))

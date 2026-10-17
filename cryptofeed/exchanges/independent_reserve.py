'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from contextlib import suppress
from datetime import datetime
from decimal import Decimal
import logging
from typing import Dict, Optional, Tuple
from collections import defaultdict
from time import time

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, BUY, ASK, INDEPENDENT_RESERVE, L3_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import Trade, OrderBook


LOG = logging.getLogger(__name__)


class IndependentReserve(Feed):
    id = INDEPENDENT_RESERVE
    provides_sequence_number = True
    validates_sequence_number = True
    SNAPSHOT_MARGIN = 1.5
    SNAPSHOT_STALENESS_WAIT = 1.5
    SNAPSHOT_STALENESS_ATTEMPTS = 8
    SNAPSHOT_BACKOFF = 30.0
    SNAPSHOT_BACKOFF_MAX = 300.0
    SNAPSHOT_TIMEOUT = 30.0
    BOOK_BUFFER_LIMIT = 10_000
    websocket_endpoints = [WebsocketEndpoint('wss://websockets.independentreserve.com')]
    rest_endpoints = [RestEndpoint('https://api.independentreserve.com', routes=Routes(['/Public/GetValidPrimaryCurrencyCodes', '/Public/GetValidSecondaryCurrencyCodes'], l3book='/Public/GetAllOrders?primaryCurrencyCode={}&secondaryCurrencyCode={}'))]

    websocket_channels = {
        L3_BOOK: 'orderbook-{}',
        TRADES: 'ticker-{}',
    }
    request_limit = 1
    _wanted = None

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
        self._order_ids = {}
        self._quotes = defaultdict(list)
        self._nonce = {}
        self._buffer = {}
        self._pending = {}
        self._ready = {}
        self._floor = {}

    async def _trade(self, msg: dict, timestamp: float):
        '''
        {
            'Channel': 'ticker-eth-aud',
            'Nonce': 78,
            'Data': {
                'TradeGuid': '6d1c2e90-592a-409c-a8d8-58b2d25e0b0b',
                'Pair': 'eth-aud',
                'TradeDate': '2022-01-31T08:28:26.552573+11:00',
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
        if msg['Channel'].lower() != f"ticker-{msg['Data']['Pair']}".lower():
            return
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
        quotes = self._quotes.get(base)
        if not quotes:
            return

        last = self._nonce.get(base)
        self._nonce[base] = seq_no
        if last is None or last + 1 != seq_no:
            if last is not None:
                LOG.warning("%s: %s missing sequence number (%d - %d) - resyncing its books from snapshots", self.id, base, last, seq_no)
            self._sync(base, quotes, msg)
            return

        buffer = self._buffer.get(base)
        if buffer is not None:
            if len(buffer) < self.BOOK_BUFFER_LIMIT:
                buffer.append(msg)
            else:
                LOG.warning("%s: %s buffered %d updates waiting for snapshots - restarting their sync", self.id, base, len(buffer))
                self._sync(base, [(quote, instrument) for quote, instrument in quotes if instrument not in self._l3_book], msg)

        update_time = msg['Time'] / 1000
        for quote, instrument in quotes:
            book = self._l3_book.get(instrument)
            if book is None or update_time < self._floor[instrument]:
                continue
            delta = self._apply(book, self._order_ids[instrument], quote, msg)
            if delta is not None:
                await self.book_callback(L3_BOOK, book, timestamp, raw=msg, sequence_number=seq_no, delta=delta, timestamp=update_time)

    def _apply(self, book: OrderBook, orders: dict, quote: str, msg: dict) -> Optional[dict]:
        delta = {BID: [], ASK: []}
        uuid = msg['Data']['OrderGuid']

        if msg['Event'] == 'OrderCanceled':
            if uuid not in orders:
                return None
            price, side = orders.pop(uuid)
            if price in book.book[side] and uuid in book.book[side][price]:
                del book.book[side][price][uuid]
                if len(book.book[side][price]) == 0:
                    del book.book[side][price]
                delta[side].append((uuid, price, Decimal(0)))
        elif msg['Event'] == 'NewOrder':
            price = Decimal(msg['Data']['Price'][quote])
            size = Decimal(msg['Data']['Volume'])
            side = BID if msg['Data']['OrderType'].endswith('Bid') else ASK
            orders[uuid] = (price, side)

            if price in book.book[side]:
                book.book[side][price][uuid] = size
            else:
                book.book[side][price] = {uuid: size}
            delta[side].append((uuid, price, size))
        elif msg['Event'] == 'OrderChanged':
            if uuid not in orders:
                return None
            price, side = orders[uuid]
            size = Decimal(msg['Data']['Volume'])

            if size == 0:
                del book.book[side][price][uuid]
                if len(book.book[side][price]) == 0:
                    del book.book[side][price]
                del orders[uuid]
            else:
                book.book[side][price][uuid] = size
            delta[side].append((uuid, price, size))
        else:
            raise ValueError("%s: Invalid OrderBook event message of type %s", self.id, msg)
        return delta

    def _sync(self, base: str, quotes: list, msg: dict):
        self._buffer[base] = [msg]
        fetch = asyncio.get_running_loop().time() + self.SNAPSHOT_STALENESS_WAIT

        for quote, instrument in quotes:
            self._l3_book.pop(instrument, None)
            self._order_ids.pop(instrument, None)
            self._ready.pop(instrument, None)
            entry = self._pending.setdefault(instrument, [base, quote, 0, fetch])
            entry[3] = max(entry[3], fetch)
        if self._wanted is not None:
            self._wanted.set()

    async def _snapshots(self):
        loop = asyncio.get_running_loop()
        self._wanted = asyncio.Event()
        next_request = 0.0

        while True:
            self._wanted.clear()
            now = loop.time()
            instrument = next((instrument for instrument, entry in self._pending.items() if entry[3] <= now), None)

            if instrument is None:
                retry = min((entry[3] for entry in self._pending.values()), default=None)
                with suppress(TimeoutError):
                    await asyncio.wait_for(self._wanted.wait(), None if retry is None else retry - now)
                continue

            if next_request > now:
                await asyncio.sleep(next_request - now)
                continue

            base, quote, attempts, _ = self._pending[instrument]
            buffer = self._buffer[base]
            next_request = now + 1 / self.request_limit
            generated = None

            try:
                async with asyncio.timeout(self.SNAPSHOT_TIMEOUT):
                    response = await self.http_conn.read(self._snapshot_url(f"{base}-{quote}"))
                received = time()
                book = self._parse_snapshot(instrument, response)
                generated = self._snapshot_generated_at(book.raw)
            except Exception as e:
                LOG.warning('%s: %s snapshot request failed: %r', self.id, instrument, e)

            if instrument not in self._pending or self._buffer.get(base) is not buffer:
                continue

            if generated is not None and generated - self.SNAPSHOT_MARGIN >= buffer[0]['Time'] / 1000:
                del self._pending[instrument]
                self._ready[instrument] = (base, quote, buffer, book, generated, received)
                continue

            attempts += 1
            if generated is not None:
                LOG.info('%s: %s snapshot was generated %.2fs after the first buffered update, less than the %.1fs margin - '
                         'trying again (attempt %d/%d)', self.id, instrument, generated - buffer[0]['Time'] / 1000,
                         self.SNAPSHOT_MARGIN, attempts, self.SNAPSHOT_STALENESS_ATTEMPTS)

            wait = self.SNAPSHOT_STALENESS_WAIT
            if attempts % self.SNAPSHOT_STALENESS_ATTEMPTS == 0:
                wait = min(self.SNAPSHOT_BACKOFF * 2 ** (attempts // self.SNAPSHOT_STALENESS_ATTEMPTS - 1), self.SNAPSHOT_BACKOFF_MAX)
                LOG.error('%s: %s could not obtain usable snapshot in %d attempts - book is unsynced, retrying in %.0fs',
                          self.id, instrument, self.SNAPSHOT_STALENESS_ATTEMPTS, wait)

            del self._pending[instrument]
            self._pending[instrument] = [base, quote, attempts, loop.time() + wait]

    async def _install(self):
        for instrument in list(self._ready):
            base, quote, buffer, book, generated, received = self._ready.pop(instrument)
            floor = generated - self.SNAPSHOT_MARGIN
            orders = {}

            for side in (BID, ASK):
                for price, level in book.book[side].items():
                    for uuid in level:
                        orders[uuid] = (price, side)

            for update in buffer:
                if update['Time'] / 1000 >= floor:
                    self._apply(book, orders, quote, update)

            self._l3_book[instrument] = book
            self._order_ids[instrument] = orders
            self._floor[instrument] = floor

            if not any(entry[0] == base for entry in (*self._pending.values(), *self._ready.values())):
                del self._buffer[base]
            await self.book_callback(L3_BOOK, book, received, timestamp=generated, raw=book.raw, sequence_number=self._nonce[base])

    def _snapshot_url(self, symbol: str) -> str:
        base, quote = symbol.split('-')
        return self.rest_endpoints[0].route('l3book', self.sandbox).format(base, quote)

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        ret = json.loads(data, parse_float=Decimal)
        book = OrderBook(self.id, symbol, max_depth=self.max_depth)

        for side, key in [(BID, 'BuyOrders'), (ASK, 'SellOrders')]:
            for order in ret[key]:
                price = Decimal(order['Price'])
                size = Decimal(order['Volume'])
                uuid = order['Guid']

                if price in book.book[side]:
                    book.book[side][price][uuid] = size
                else:
                    book.book[side][price] = {uuid: size}
        book.raw = ret
        return book

    @staticmethod
    def _snapshot_generated_at(raw: dict) -> float:
        return datetime.fromisoformat(raw['CreatedTimestampUtc'].replace('Z', '+00:00')).timestamp()

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['Event'] == 'Trade':
            await self._trade(msg, timestamp)
        elif msg['Event'] in ('OrderCanceled', 'OrderChanged', 'NewOrder'):
            await self._book(msg, timestamp)
        elif msg['Event'] not in ('Subscriptions', 'Heartbeat', 'Unsubscribe'):
            LOG.warning("%s: Invalid message type %s", self.id, msg)

        if self._pending:
            await asyncio.sleep(0)
        if self._ready:
            await self._install()

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        subs = []
        for chan, symbols in conn.subscription.items():
            if self.exchange_channel_to_std(chan) == L3_BOOK:
                subs.extend([chan.format(s) for s in set([sym.split("-")[0] for sym in symbols])])

                for sym in symbols:
                    base, quote = sym.split('-')
                    self._quotes[base].append((quote, self.exchange_symbol_to_std_symbol(sym)))

                self._spawn('snapshots', self._snapshots)

            else:
                subs.extend([chan.format(s) for s in symbols])

        await conn.write(json.dumps({"Event": "Subscribe", "Data": subs}))

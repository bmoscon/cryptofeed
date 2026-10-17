'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Optional, Tuple

from cryptofeed import _json as json
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BID, BUY, L1_BOOK, L2_BOOK, MEXC, SELL, SPOT, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import L1Book, OrderBook, Trade
from cryptofeed.util.snapshots import SnapshotSync


LOG = logging.getLogger(__name__)


def _varint(buf: bytes, index: int) -> Tuple[int, int]:
    shift = result = 0
    while True:
        byte = buf[index]
        index += 1
        result |= (byte & 0x7F) << shift
        if not byte & 0x80:
            return result, index
        shift += 7


def _fields(buf: bytes):
    index = 0
    length = len(buf)
    while index < length:
        key, index = _varint(buf, index)
        number, wire = key >> 3, key & 7
        if wire == 0:
            value, index = _varint(buf, index)
        elif wire == 2:
            size, index = _varint(buf, index)
            value, index = buf[index:index + size], index + size
        elif wire == 5:
            index += 4
            continue
        elif wire == 1:
            index += 8
            continue
        else:
            return
        yield number, value


def _one(buf: bytes) -> dict:
    return dict(_fields(buf))

def _levels(buf: bytes, number: int) -> list:
    out = []
    for field, value in _fields(buf):
        if field != number:
            continue
        level = _one(value)
        out.append((Decimal(level[1].decode()), Decimal(level[2].decode())))
    return out


class MEXCSpot(SnapshotSync, Feed):
    id = MEXC
    websocket_endpoints = [WebsocketEndpoint('wss://wbs-api.mexc.com/ws', limit=20)]
    rest_endpoints = [RestEndpoint('https://api.mexc.com', routes=Routes('/api/v3/exchangeInfo', l2book='/api/v3/depth?symbol={}&limit={}'))]
    websocket_channels = {
        L2_BOOK: 'spot@public.aggre.depth.v3.api.pb@100ms',
        TRADES: 'spot@public.aggre.deals.v3.api.pb@100ms',
        L1_BOOK: 'spot@public.aggre.bookTicker.v3.api.pb@100ms',
    }
    request_limit = 20
    provides_sequence_number = True
    validates_sequence_number = True
    provides_checksum = False

    DEALS = 314
    DEPTH = 313
    BOOK_TICKER = 315
    SNAPSHOT_DEPTH = 2000

    @classmethod
    def timestamp_normalize(cls, ts: int) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['symbols']:
            if entry.get('status') != '1':
                continue
            symbol = Symbol(entry['baseAsset'], entry['quoteAsset'], type=SPOT)
            info['instrument_type'][symbol.normalized] = SPOT
            ret[symbol.normalized] = entry['symbol']
        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sync_init()
        self._reset()

    def _reset(self):
        self._cancel_syncs()
        self._l2_book = {}
        self.last_update_id = {}

    async def subscribe(self, conn: AsyncConnection):
        for symbol in conn.subscription.get(self.websocket_channels[L2_BOOK], []):
            self._resync(self.exchange_symbol_to_std_symbol(symbol))
        self._cancel_syncs(getattr(conn, 'uuid', None))
        topics = [f'{channel}@{symbol}'
                  for channel, symbols in conn.subscription.items() for symbol in symbols]
        for start in range(0, len(topics), 30):
            await conn.write(json.dumps({'method': 'SUBSCRIPTION', 'params': topics[start:start + 30]}))

    async def _trades(self, symbol: str, payload: bytes, timestamp: float):
        for field, value in _fields(payload):
            if field != 1:
                continue
            deal = _one(value)
            trade = Trade(
                self.id,
                symbol,
                BUY if deal.get(3) == 1 else SELL,
                Decimal(deal[2].decode()),
                Decimal(deal[1].decode()),
                self.timestamp_normalize(deal[4]),
                id=deal[5].decode() if 5 in deal else None,
                raw={'price': deal[1].decode(), 'quantity': deal[2].decode(), 'tradeType': deal.get(3), 'time': deal.get(4), 'tradeId': deal[5].decode() if 5 in deal else None}
            )
            await self.callback(TRADES, trade, timestamp)

    async def _l1_book(self, symbol: str, payload: bytes, timestamp: float, send_time: Optional[int]):
        book = _one(payload)
        if not all(key in book for key in (1, 2, 3, 4)):
            return
        await self.callback(L1_BOOK, L1Book(self.id,
                                            symbol,
                                            Decimal(book[1].decode()),
                                            Decimal(book[2].decode()),
                                            Decimal(book[3].decode()),
                                            Decimal(book[4].decode()),
                                            self.timestamp_normalize(send_time) if send_time is not None else timestamp,
                                            raw={'version': int(book[5].decode()) if 5 in book else None,
                                                 'lastOrderCreateTime': book.get(6), 'sendTime': send_time}),
                                            timestamp)

    def _snapshot_url(self, symbol: str) -> str:
        return self.rest_endpoints[0].route('l2book').format(symbol, self.SNAPSHOT_DEPTH)

    def _parse_snapshot(self, symbol: str, data) -> OrderBook:
        data = json.loads(data, parse_float=Decimal)
        book = OrderBook(self.id, symbol, max_depth=self.max_depth)
        book.book.bids = {Decimal(price): Decimal(size) for price, size in data['bids']}
        book.book.asks = {Decimal(price): Decimal(size) for price, size in data['asks']}
        book.sequence_number = data['lastUpdateId']
        book.timestamp = self.timestamp_normalize(data['timestamp']) if data.get('timestamp') else None
        return book

    @staticmethod
    def _versions(update: tuple) -> Tuple[Optional[int], Optional[int]]:
        message = _one(update[0])
        return (int(message[4].decode()) if 4 in message else None, int(message[5].decode()) if 5 in message else None)

    def _covered(self, sequence: int, update: tuple) -> bool:
        return (self._versions(update)[1] or sequence + 1) <= sequence

    def _bridges(self, sequence: int, update: tuple) -> bool:
        from_version = self._versions(update)[0]
        return from_version is None or from_version <= sequence + 1

    def _start_book(self, symbol: str, book: OrderBook):
        self._l2_book[symbol] = book
        self.last_update_id[symbol] = book.sequence_number

    async def _apply_buffered(self, pair: str, update: tuple, timestamp: float, conn):
        payload, send_time = update
        await self._book(self.exchange_symbol_to_std_symbol(pair), payload, timestamp, send_time, conn)

    def _apply(self, symbol: str, payload: bytes, timestamp: float, send_time: Optional[int]):
        message = _one(payload)
        to_version = int(message[5].decode()) if 5 in message else None
        from_version = int(message[4].decode()) if 4 in message else None
        last = self.last_update_id.get(symbol)

        if to_version is not None and last is not None:
            if to_version <= last:
                return None
            if from_version is not None and from_version > last + 1:
                raise MissingSequenceNumber(f"{self.id}: expected sequence number {last+1}, got {from_version}")
            self.last_update_id[symbol] = to_version

        book = self._l2_book[symbol]
        delta = {BID: [], ASK: []}
        for side, number in ((ASK, 1), (BID, 2)):
            for price, size in _levels(payload, number):
                if size == 0:
                    if price in book.book[side]:
                        del book.book[side][price]
                else:
                    book.book[side][price] = size
                delta[side].append((price, size))
        return delta, {'fromVersion': from_version, 'toVersion': to_version, 'sendTime': send_time,
                       'lastOrderCreateTime': message.get(6)}

    def _resync(self, symbol: str):
        self._l2_book.pop(symbol, None)
        self.last_update_id.pop(symbol, None)

    async def _book(self, symbol: str, payload: bytes, timestamp: float, send_time: Optional[int], conn=None):
        if symbol not in self._l2_book:
            self._buffer_update(self.std_symbol_to_exchange_symbol(symbol), symbol, (payload, send_time), conn)
            return

        try:
            applied = self._apply(symbol, payload, timestamp, send_time)
        except MissingSequenceNumber as e:
            LOG.warning('%s: %s missing sequence number for %s', self.id, e, symbol)
            self.book_sync_stats['gap_resets'] += 1
            self._resync(symbol)
            await self._book(symbol, payload, timestamp, send_time, conn)
            return
        if applied is not None:
            delta, raw = applied
            await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, delta=delta, raw=raw,
                                     sequence_number=raw['toVersion'],
                                     timestamp=self.timestamp_normalize(send_time) if send_time is not None else None)

    async def message_handler(self, msg, conn: AsyncConnection, timestamp: float):
        if self._ready:
            await self._install_snapshots(conn, timestamp)
        await self._handle(msg, conn, timestamp)
        if self._syncing:
            await asyncio.sleep(0)

    async def _handle(self, msg, conn: AsyncConnection, timestamp: float):
        if not isinstance(msg, bytes):
            ack = json.loads(msg)
            if ack.get('code') not in (0, None):
                LOG.error('%s: %s', self.id, ack.get('msg'))
            return

        wrapper = _one(msg)
        channel = wrapper.get(1, b'').decode(errors='replace')
        if 3 not in wrapper:
            LOG.warning('%s: message with no symbol on %s', self.id, channel)
            return
        symbol = self.exchange_symbol_to_std_symbol(wrapper[3].decode())
        send_time = wrapper.get(6)

        if self.DEALS in wrapper:
            await self._trades(symbol, wrapper[self.DEALS], timestamp)
        elif self.DEPTH in wrapper:
            await self._book(symbol, wrapper[self.DEPTH], timestamp, send_time, conn)
        elif self.BOOK_TICKER in wrapper:
            await self._l1_book(symbol, wrapper[self.BOOK_TICKER], timestamp, send_time)
        else:
            LOG.warning('%s: no known payload on %s (fields %s)', self.id, channel, sorted(wrapper))

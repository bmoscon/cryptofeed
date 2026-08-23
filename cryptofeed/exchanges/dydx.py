'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from collections import defaultdict
from decimal import Decimal
from typing import Dict, Tuple

from cryptofeed import _json as json
from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BID, BUY, DYDX, L2_BOOK, PERPETUAL, SELL, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade


LOG = logging.getLogger(__name__)


class dYdX(Feed):
    id = DYDX
    CROSSED_BOOKS_ARE_DOCUMENTED = True
    SEQUENCED_FRAMES = ('channel_data', 'channel_batch_data')

    websocket_endpoints = [WebsocketEndpoint('wss://indexer.dydx.trade/v4/ws', limit=4)]
    rest_endpoints = [RestEndpoint('https://indexer.dydx.trade', routes=Routes('/v4/perpetualMarkets'))]

    websocket_channels = {
        L2_BOOK: 'v4_orderbook',
        TRADES: 'v4_trades',
    }
    request_limit = 10
    provides_sequence_number = False
    provides_checksum = False

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for ticker, entry in data['markets'].items():
            if entry.get('status') != 'ACTIVE':
                continue
            base = ticker.rsplit('-', 1)[0]
            symbol = Symbol(base, 'USD', type=PERPETUAL)
            info['instrument_type'][symbol.normalized] = PERPETUAL
            info['tick_size'][symbol.normalized] = Decimal(entry['tickSize'])
            ret[symbol.normalized] = ticker
        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._reset()

    def _reset(self):
        self._l2_book = {}
        self._message_id = {}

    async def subscribe(self, conn: AsyncConnection):
        self._reset()
        for channel, symbols in conn.subscription.items():
            for symbol in symbols:
                await conn.write(json.dumps({'type': 'subscribe', 'channel': channel, 'id': symbol}))

    async def _trades(self, msg: dict, timestamp: float):
        symbol = self.exchange_symbol_to_std_symbol(msg['id'])
        for entry in msg['contents']['trades']:
            trade = Trade(
                self.id,
                symbol,
                BUY if entry['side'] == 'BUY' else SELL,
                Decimal(entry['size']),
                Decimal(entry['price']),
                self.timestamp_normalize(entry['createdAt']),
                id=entry['id'],
                type=entry.get('type'),
                raw=entry
            )

            await self.callback(TRADES, trade, timestamp)

    async def _snapshot(self, msg: dict, timestamp: float):
        symbol = self.exchange_symbol_to_std_symbol(msg['id'])
        contents = msg['contents']
        self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)
        self._l2_book[symbol].book.bids = {Decimal(level['price']): Decimal(level['size']) for level in contents.get('bids', []) if Decimal(level['size']) > 0}
        self._l2_book[symbol].book.asks = {Decimal(level['price']): Decimal(level['size']) for level in contents.get('asks', []) if Decimal(level['size']) > 0}

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, raw=msg)

    async def _update(self, msg: dict, timestamp: float):
        symbol = self.exchange_symbol_to_std_symbol(msg['id'])
        if symbol not in self._l2_book:
            return

        book = self._l2_book[symbol]
        delta = {BID: [], ASK: []}
        for side, key in ((BID, 'bids'), (ASK, 'asks')):
            for price, size in msg['contents'].get(key, []):
                price, size = Decimal(price), Decimal(size)
                if size == 0:
                    if price in book.book[side]:
                        del book.book[side][price]
                else:
                    book.book[side][price] = size
                delta[side].append((price, size))

        await self.book_callback(L2_BOOK, book, timestamp, delta=delta, raw=msg)

    def _check_sequence_number(self, msg: dict, conn: AsyncConnection) -> None:
        if msg.get('type') not in self.SEQUENCED_FRAMES:
            return
        message_id = msg.get('message_id')
        uuid = getattr(conn, 'uuid', None)
        if message_id is None or uuid is None:
            return

        last = self._message_id.get(uuid)
        self._message_id[uuid] = message_id
        if last is not None and message_id != last + 1:
            if message_id <= last:
                LOG.warning('%s: %s message_id went backwards, %s after %s', self.id, uuid, message_id, last)
                return
            raise MissingSequenceNumber(f"{self.id}: expected sequence number {last}, got {message_id}")

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)
        self._check_sequence_number(msg, conn)
        kind, channel = msg.get('type'), msg.get('channel')

        if kind == 'channel_data' or kind == 'channel_batch_data':
            if channel == 'v4_trades':
                await self._trades(msg, timestamp)
            elif channel == 'v4_orderbook':
                await self._update(msg, timestamp)
            else:
                LOG.warning('%s: unexpected data channel %s', self.id, channel)
        elif kind == 'subscribed':
            if channel == 'v4_orderbook':
                await self._snapshot(msg, timestamp)
            elif channel == 'v4_trades':
                LOG.info('%s: discarding the %d-trade history batch for %s - it is a history query, not reconnect backfill', self.id, len(msg.get('contents', {}).get('trades', [])), msg.get('id'))
        elif kind == 'connected':
            LOG.debug('%s: connected, connection_id %s', self.id, msg.get('connection_id'))
        elif kind == 'error':
            LOG.error('%s: venue reported an error: %s', self.id, msg.get('message'))
        elif kind in ('unsubscribed', 'pong'):
            pass
        else:
            LOG.warning('%s: unexpected message %s', self.id, msg)

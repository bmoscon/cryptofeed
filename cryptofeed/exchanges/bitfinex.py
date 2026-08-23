'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
from functools import partial
import logging
from typing import Dict, Tuple

from cryptofeed import _json as json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BITFINEX, BUY, CURRENCY, FUNDING, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES, PERPETUAL
from cryptofeed.exceptions import BadChecksum, MissingSequenceNumber, UnsupportedDataFeed
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import Ticker, Trade, OrderBook


LOG = logging.getLogger(__name__)

"""
Bitfinex configuration flags
DEC_S: Enable all decimal as strings.
TIME_S: Enable all times as date strings.
TIMESTAMP: Timestamp in milliseconds.
SEQ_ALL: Enable sequencing BETA FEATURE
CHECKSUM: Enable checksum for every book iteration.
          Checks the top 25 entries for each side of book.
          Checksum is a signed int.
"""
DEC_S = 8
TIME_S = 32
TIMESTAMP = 32768
SEQ_ALL = 65536
CHECKSUM = 131072


class Bitfinex(Feed):
    id = BITFINEX
    provides_checksum = True
    provides_sequence_number = True
    validates_sequence_number = True

    websocket_endpoints = [WebsocketEndpoint('wss://api-pub.bitfinex.com/ws/2', limit=20)]
    rest_endpoints = [RestEndpoint('https://api-pub.bitfinex.com', routes=Routes(['/v2/conf/pub:list:pair:exchange', '/v2/conf/pub:list:currency', '/v2/conf/pub:list:pair:futures']))]
    websocket_channels = {
        L3_BOOK: 'book-R0-{}-{}',
        L2_BOOK: 'book-P0-{}-{}',
        TRADES: 'trades',
        TICKER: 'ticker',
    }
    request_limit = 1

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    asset_aliases = {'BCHN': 'BCH', 'UST': 'USDT'}

    @classmethod
    def _asset(cls, code: str) -> str:
        return cls.asset_aliases.get(code, code)

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        # https://docs.bitfinex.com/docs/ws-general#supported-pairs
        ret = {}
        info = {'instrument_type': {}}

        pairs = data[0][0]
        currencies = data[1][0]
        perpetuals = data[2][0]

        for c in sorted(currencies, key=lambda code: code in cls.asset_aliases):
            asset = cls._asset(c)
            s = Symbol(asset, asset, type=CURRENCY)
            ret[s.normalized] = "f" + c
            info['instrument_type'][s.normalized] = CURRENCY

        for p in pairs:
            if ':' in p:
                base, quote = p.split(":")
            else:
                base, quote = p[:3], p[3:]

            s = Symbol(cls._asset(base), cls._asset(quote))
            ret[s.normalized] = "t" + p
            info['instrument_type'][s.normalized] = s.type

        for f in perpetuals:
            base, quote = f.split(':')  # 'ALGF0:USTF0'
            s = Symbol(cls._asset(base[:-2]), cls._asset(quote[:-2]), type=PERPETUAL)
            ret[s.normalized] = "t" + f
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, symbols=None, channels=None, subscription=None, number_of_price_points: int = 100, book_frequency: str = 'F0', **kwargs):
        if number_of_price_points not in {1, 25, 100, 250}:
            raise ValueError("number_of_price_points should be one of 1, 25, 100, 250")
        if book_frequency not in {'F0', 'F1'}:
            raise ValueError("book_frequency should be one of F0, F1")

        super().__init__(symbols=symbols, channels=channels, subscription=subscription, **kwargs)
        self.number_of_price_points = number_of_price_points
        self.book_frequency = book_frequency
        self.handlers = {}  # maps a channel id to a function
        self.order_map = defaultdict(dict)
        self.seq_no = defaultdict(int)

    def _subscription_resolved(self):
        for channel in (L2_BOOK, L3_BOOK):
            funding = [symbol for symbol in self.subscription.get(self.std_channel_to_exchange(channel), []) if symbol[0] == 'f']
            if funding:
                raise UnsupportedDataFeed(f'{self.id} does not serve {channel} for funding currencies: {sorted(self.exchange_symbol_to_std_symbol(s) for s in funding)}')

        channels = self._init_channels
        subscription = self._init_subscription
        symbols = self._init_symbols
        if channels or subscription:
            for chan in set(channels or subscription):
                for pair in set(subscription[chan] if subscription else symbols or []):
                    exch_sym = self.std_symbol_to_exchange_symbol(pair)
                    if (exch_sym[0] == 'f') == (chan != FUNDING):
                        LOG.warning('%s: No %s for symbol %s => Cryptofeed will subscribe to the wrong channel', self.id, chan, pair)

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

        if conn.uuid in self.seq_no:
            del self.seq_no[conn.uuid]

        if self.std_channel_to_exchange(L3_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L3_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l3_book:
                    del self._l3_book[std_pair]

                if std_pair in self.order_map:
                    del self.order_map[std_pair]

    async def _ticker(self, pair: str, msg: list, timestamp: float):
        if msg[1] == 'hb':
            return  # ignore heartbeats
        # bid, bid_size, ask, ask_size, daily_change, daily_change_percent,
        # last_price, volume, high, low - and Bitfinex has since appended an 11th field, so index
        # rather than unpack: a positional unpack raises ValueError the moment the venue adds one
        bid, ask = msg[1][0], msg[1][2]
        t = Ticker(self.id, pair, Decimal(bid), Decimal(ask), None, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _funding_ticker(self, pair: str, msg: list, timestamp: float):
        if msg[1] == 'hb':
            return
        bid, ask = msg[1][1], msg[1][4]
        t = Ticker(self.id, pair, Decimal(bid), Decimal(ask), None, raw=msg)
        await self.callback(TICKER, t, timestamp)

    async def _funding(self, pair: str, msg: list, timestamp: float):
        async def _funding_update(funding: list, timestamp: float):
            order_id, ts, amount, price, period = funding
            t = Trade(
                self.id,
                pair,
                SELL if amount < 0 else BUY,
                Decimal(abs(Decimal(amount))),
                Decimal(price),
                self.timestamp_normalize(ts),
                id=str(order_id),
                raw=funding
            )
            await self.callback(TRADES, t, timestamp)

        if isinstance(msg[1], list):
            # snapshot
            for funding in msg[1]:
                await _funding_update(funding, timestamp)
        elif msg[1] in ('te', 'fte'):
            # update
            await _funding_update(msg[2], timestamp)
        elif msg[1] not in ('tu', 'ftu', 'hb'):
            # ignore trade updates and heartbeats
            LOG.warning('%s %s: Unexpected funding message %s', self.id, pair, msg)

    async def _trades(self, pair: str, msg: list, timestamp: float):
        async def _trade_update(trade: list, timestamp: float):
            order_id, ts, amount, price = trade
            t = Trade(
                self.id,
                pair,
                SELL if amount < 0 else BUY,
                Decimal(abs(Decimal(amount))),
                Decimal(price),
                self.timestamp_normalize(ts),
                id=str(order_id),
            )
            await self.callback(TRADES, t, timestamp)

        if isinstance(msg[1], list):
            # snapshot
            for trade in msg[1]:
                await _trade_update(trade, timestamp)
        elif msg[1] in ('te', 'fte'):
            # update
            await _trade_update(msg[2], timestamp)
        elif msg[1] not in ('tu', 'ftu', 'hb'):
            # ignore trade updates and heartbeats
            LOG.warning('%s %s: Unexpected trade message %s', self.id, pair, msg)

    async def _book(self, pair: str, msg: list, timestamp: float):
        """For L2 book updates."""
        if not isinstance(msg[1], list):
            if msg[1] == 'cs':
                if self.checksum_validation and pair in self._l2_book and self._l2_book[pair].book.checksum() != msg[2] & 0xFFFFFFFF:
                    raise BadChecksum(f'{self.id} {pair}: book checksum mismatch')
                return
            if msg[1] != 'hb':
                LOG.warning('%s: Unexpected book L2 msg %s', self.id, msg)
            return

        delta = None
        if isinstance(msg[1][0], list):
            # snapshot so clear book
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, checksum_format=self.id)
            for update in msg[1]:
                price, _, amount = update
                price = Decimal(price)
                amount = Decimal(amount)

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = abs(amount)
                self._l2_book[pair].book[side][price] = amount
        else:
            # book update
            delta = {BID: [], ASK: []}
            price, count, amount = msg[1]
            price = Decimal(price)
            amount = Decimal(amount)

            if amount > 0:
                side = BID
            else:
                side = ASK
                amount = abs(amount)

            if count > 0:
                # change at price level
                delta[side].append((price, amount))
                self._l2_book[pair].book[side][price] = amount
            else:
                # remove price level
                if price in self._l2_book[pair].book[side]:
                    del self._l2_book[pair].book[side][price]
                    delta[side].append((price, 0))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg, delta=delta, sequence_number=msg[-1])

    async def _raw_book(self, pair: str, msg: list, timestamp: float):
        """For L3 book updates."""
        if not isinstance(msg[1], list):
            if msg[1] == 'cs':
                if self.checksum_validation and pair in self._l3_book and self._l3_book[pair].book.checksum() != msg[2] & 0xFFFFFFFF:
                    raise BadChecksum(f'{self.id} {pair}: book checksum mismatch')
                return
            if msg[1] != 'hb':
                LOG.warning('%s: Unexpected book L3 msg %s', self.id, msg)
            return

        def add_to_book(side, price, order_id, amount):
            if price in self._l3_book[pair].book[side]:
                self._l3_book[pair].book[side][price][order_id] = amount
            else:
                self._l3_book[pair].book[side][price] = {order_id: amount}

        def remove_from_book(side, order_id):
            price = self.order_map[pair][side][order_id]['price']
            del self._l3_book[pair].book[side][price][order_id]
            if len(self._l3_book[pair].book[side][price]) == 0:
                del self._l3_book[pair].book[side][price]

        delta = None

        if isinstance(msg[1][0], list):
            # snapshot so clear orders
            self.order_map[pair][BID] = {}
            self.order_map[pair][ASK] = {}
            self._l3_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, checksum_format=self.id)

            for update in msg[1]:
                order_id, price, amount = update
                price = Decimal(price)
                amount = Decimal(amount)

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = - amount

                self.order_map[pair][side][order_id] = {'price': price, 'amount': amount}
                add_to_book(side, price, order_id, amount)
        else:
            # book update
            delta = {BID: [], ASK: []}
            order_id, price, amount = msg[1]
            price = Decimal(price)
            amount = Decimal(amount)

            if amount > 0:
                side = BID
            else:
                side = ASK
                amount = abs(amount)

            if price == 0:
                price = self.order_map[pair][side][order_id]['price']
                remove_from_book(side, order_id)
                del self.order_map[pair][side][order_id]
                delta[side].append((order_id, price, 0))
            else:
                if order_id in self.order_map[pair][side]:
                    del_price = self.order_map[pair][side][order_id]['price']
                    delta[side].append((order_id, del_price, 0))
                    # remove existing order before adding new one
                    delta[side].append((order_id, price, amount))
                    remove_from_book(side, order_id)
                else:
                    delta[side].append((order_id, price, amount))
                add_to_book(side, price, order_id, amount)
                self.order_map[pair][side][order_id] = {'price': price, 'amount': amount}

        await self.book_callback(L3_BOOK, self._l3_book[pair], timestamp, raw=msg, delta=delta, sequence_number=msg[-1])

    @staticmethod
    async def _do_nothing(msg: list, timestamp: float):
        pass

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg, list):
            hb_skip = False
            chan_handler = self.handlers.get(msg[0])
            if chan_handler is None:
                if msg[1] == 'hb':
                    hb_skip = True
                else:
                    LOG.warning('%s: Unregistered channel ID in message %s', conn.uuid, msg)
                    return
            seq_no = msg[-1]
            expected = self.seq_no[conn.uuid] + 1
            if seq_no != expected:
                LOG.warning('%s: missed message (sequence number) received %s, expected %s', conn.uuid, seq_no, expected)
                raise MissingSequenceNumber
            self.seq_no[conn.uuid] = seq_no
            if hb_skip:
                return
            await chan_handler(msg, timestamp)

        elif 'event' not in msg:
            LOG.warning('%s: Unexpected msg (missing event) from exchange: %s', conn.uuid, msg)
        elif msg['event'] == 'error':
            LOG.error('%s: Error from exchange: %s', conn.uuid, msg)
        elif msg['event'] in ('info', 'conf'):
            LOG.debug('%s: %s from exchange: %s', conn.uuid, msg['event'], msg)
        elif 'chanId' in msg and 'symbol' in msg:
            self.register_channel_handler(msg, conn)
        else:
            LOG.warning('%s: Unexpected msg from exchange: %s', conn.uuid, msg)

    def register_channel_handler(self, msg: dict, conn: AsyncConnection):
        symbol = msg['symbol']
        is_funding = (symbol[0] == 'f')
        pair = self.exchange_symbol_to_std_symbol(symbol)

        if msg['channel'] == 'ticker':
            handler = partial(self._funding_ticker if is_funding else self._ticker, pair)
        elif msg['channel'] == 'trades':
            if is_funding:
                handler = partial(self._funding, pair)
            else:
                handler = partial(self._trades, pair)
        elif msg['channel'] == 'book':
            if is_funding:
                LOG.warning('%s %s: funding books - ignoring %s', conn.uuid, pair, msg)
                handler = self._do_nothing
            elif msg['prec'] == 'R0':
                handler = partial(self._raw_book, pair)
            else:
                handler = partial(self._book, pair)
        else:
            LOG.warning('%s %s: Unexpected message %s', conn.uuid, pair, msg)
            return

        LOG.debug('%s: Register channel=%s pair=%s funding=%s %s -> %s()', conn.uuid, msg['channel'], pair, is_funding,
                  '='.join(list(msg.items())[-1]), handler.__name__ if hasattr(handler, '__name__') else handler.func.__name__)
        self.handlers[msg['chanId']] = handler

    async def subscribe(self, connection: AsyncConnection):
        self.__reset(connection)
        await connection.write(json.dumps({
            'event': "conf",
            'flags': SEQ_ALL | CHECKSUM
        }))

        for chan, pairs in connection.subscription.items():
            for pair in pairs:
                message = {'event': 'subscribe',
                           'channel': chan,
                           'symbol': pair
                           }
                if 'book' in chan:
                    parts = chan.split('-')
                    if len(parts) != 1:
                        message['channel'] = 'book'
                        try:
                            message['prec'] = parts[1]
                            message['freq'] = self.book_frequency
                            message['len'] = self.number_of_price_points
                        except IndexError:
                            # any non specified params will be defaulted
                            pass

                await connection.write(json.dumps(message))

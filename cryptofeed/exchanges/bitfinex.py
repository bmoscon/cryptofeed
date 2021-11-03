'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
from functools import partial
import logging
from typing import Callable, Dict, List, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BITFINEX, BUY, CURRENCY, FUNDING, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES, PERPETUAL
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.bitfinex_rest import BitfinexRestMixin
from cryptofeed.types import Ticker, Trade, OrderBook


LOG = logging.getLogger('feedhandler')

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


class Bitfinex(Feed, BitfinexRestMixin):
    id = BITFINEX
    symbol_endpoint = [
        'https://api-pub.bitfinex.com/v2/conf/pub:list:pair:exchange',
        'https://api-pub.bitfinex.com/v2/conf/pub:list:currency',
        'https://api-pub.bitfinex.com/v2/conf/pub:list:pair:futures',
    ]
    websocket_channels = {
        L3_BOOK: 'book-R0-{}-{}',
        L2_BOOK: 'book-P0-{}-{}',
        TRADES: 'trades',
        TICKER: 'ticker',
    }
    request_limit = 1
    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '3h', '6h', '12h', '1d', '1w', '2w', '1M'}

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        # https://docs.bitfinex.com/docs/ws-general#supported-pairs
        ret = {}
        info = {'instrument_type': {}}

        pairs = data[0][0]
        currencies = data[1][0]
        perpetuals = data[2][0]
        for c in currencies:
            c = c.replace('BCHN', 'BCH')  # Bitfinex uses BCHN, other exchanges use BCH
            c = c.replace('UST', 'USDT')
            s = Symbol(c, c, type=CURRENCY)
            ret[s.normalized] = "f" + c
            info['instrument_type'][s.normalized] = CURRENCY

        for p in pairs:
            norm = p.replace('BCHN', 'BCH')
            norm = norm.replace('UST', 'USDT')

            if ':' in norm:
                base, quote = norm.split(":")
            else:
                base, quote = norm[:3], norm[3:]

            s = Symbol(base, quote)
            ret[s.normalized] = "t" + p
            info['instrument_type'][s.normalized] = s.type

        for f in perpetuals:
            norm = f.replace('BCHN', 'BCH')
            norm = norm.replace('UST', 'USDT')
            base, quote = norm.split(':')  # 'ALGF0:USTF0'
            base, quote = base[:-2], quote[:-2]
            s = Symbol(base, quote, type=PERPETUAL)
            ret[s.normalized] = "t" + f
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, symbols=None, channels=None, subscription=None, number_of_price_points: int = 100,
                 book_frequency: str = 'F0', **kwargs):
        if number_of_price_points not in (1, 25, 100, 250):
            raise ValueError("number_of_price_points should be in 1, 25, 100, 250")
        if book_frequency not in ('F0', 'F1'):
            raise ValueError("book_frequency should be in F0, F1")

        if symbols is not None and channels is not None:
            super().__init__('wss://api.bitfinex.com/ws/2', symbols=symbols, channels=channels, **kwargs)
        else:
            super().__init__('wss://api.bitfinex.com/ws/2', subscription=subscription, **kwargs)

        self.number_of_price_points = number_of_price_points
        self.book_frequency = book_frequency
        if channels or subscription:
            for chan in set(channels or subscription):
                for pair in set(subscription[chan] if subscription else symbols or []):
                    exch_sym = self.std_symbol_to_exchange_symbol(pair)
                    if (exch_sym[0] == 'f') == (chan != FUNDING):
                        LOG.warning('%s: No %s for symbol %s => Cryptofeed will subscribe to the wrong channel', self.id, chan, pair)
        self.__reset()

    def __reset(self):
        self._l2_book = {}
        self._l3_book = {}
        self.handlers = {}  # maps a channel id (int) to a function
        self.order_map = defaultdict(dict)
        self.seq_no = defaultdict(int)

    async def _ticker(self, pair: str, msg: list, timestamp: float):
        if msg[1] == 'hb':
            return  # ignore heartbeats
        # bid, bid_size, ask, ask_size, daily_change, daily_change_percent,
        # last_price, volume, high, low
        bid, _, ask, _, _, _, _, _, _, _ = msg[1]
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
                id=order_id,
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
            if msg[1] != 'hb':
                LOG.warning('%s: Unexpected book L2 msg %s', self.id, msg)
            return

        delta = None
        if isinstance(msg[1][0], list):
            # snapshot so clear book
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
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

        delta = {BID: [], ASK: []}

        if isinstance(msg[1][0], list):
            # snapshot so clear orders
            self.order_map[pair][BID] = {}
            self.order_map[pair][ASK] = {}
            self._l3_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)

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
                LOG.warning('%s: missed message (sequence number) received %d, expected %d', conn.uuid, seq_no, expected)
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
            if is_funding:
                LOG.warning('%s %s: Ticker funding not implemented - ignoring for %s', conn.uuid, pair, msg)
                handler = self._do_nothing
            else:
                handler = partial(self._ticker, pair)
        elif msg['channel'] == 'trades':
            if is_funding:
                handler = partial(self._funding, pair)
            else:
                handler = partial(self._trades, pair)
        elif msg['channel'] == 'book':
            if msg['prec'] == 'R0':
                handler = partial(self._raw_book, pair)
            elif is_funding:
                LOG.warning('%s %s: Book funding not implemented - ignoring for %s', conn.uuid, pair, msg)
                handler = self._do_nothing
            else:
                handler = partial(self._book, pair)
        else:
            LOG.warning('%s %s: Unexpected message %s', conn.uuid, pair, msg)
            return

        LOG.debug('%s: Register channel=%s pair=%s funding=%s %s -> %s()', conn.uuid, msg['channel'], pair, is_funding,
                  '='.join(list(msg.items())[-1]), handler.__name__ if hasattr(handler, '__name__') else handler.func.__name__)
        self.handlers[msg['chanId']] = handler

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        """
        Bitfinex only supports 25 pair/channel combinations per websocket, so
        if we require more we need to create more connections

        Furthermore, the sequence numbers bitfinex provides are per-connection
        so we need to bind our connection id to the message handler
        so we know to which connextion the sequence number belongs.
        """
        pair_channel = []
        ret = []

        def build(options: list):
            subscribe = partial(self.subscribe, options=options)
            conn = WSAsyncConn(self.address, self.id, **self.ws_defaults)
            return conn, subscribe, self.message_handler, self.authenticate

        for channel in self.subscription:
            for pair in self.subscription[channel]:
                pair_channel.append((pair, channel))
                # Bitfinex max is 25 per connection
                if len(pair_channel) == 25:
                    ret.append(build(pair_channel))
                    pair_channel = []

        if len(pair_channel) > 0:
            ret.append(build(pair_channel))

        return ret

    async def subscribe(self, connection: AsyncConnection, options: List[Tuple[str, str]] = None):
        self.__reset()
        await connection.write(json.dumps({
            'event': "conf",
            'flags': SEQ_ALL
        }))

        for pair, chan in options:
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

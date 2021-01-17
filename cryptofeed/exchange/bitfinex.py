'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from decimal import Decimal
import random
from functools import partial
import logging
from typing import List, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BITFINEX, BUY, FUNDING, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.standards import symbol_exchange_to_std, timestamp_normalize
from cryptofeed.symbols import gen_symbols
from cryptofeed.util import split

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


class Bitfinex(Feed):
    id = BITFINEX

    def __init__(self, symbols=None, channels=None, subscription=None, **kwargs):
        # TRADES and FUNDING use the same subscription channel, only the first symbol character distinguishes them
        # => Warn when symbols will be subscribed to the wrong channel
        symbols_exch_to_std = gen_symbols(BITFINEX)
        for chan in set(channels or subscription):
            for pair in set(subscription[chan] if subscription else symbols or []):
                exch_sym = symbols_exch_to_std.get(pair)
                if (exch_sym[0] == 'f') == (chan != FUNDING):
                    LOG.warning('%s: No %s for symbol %s => Cryptofeed will subscribe to the wrong channel', self.id, chan, pair)

        super().__init__('wss://api.bitfinex.com/ws/2', **kwargs)
        self.address = self._address('wss://api.bitfinex.com/ws/2')

    def _address(self, ws_endpoint):
        """
        Bitfinex only supports 25 pair/channel combinations per websocket, so
        if we require more we need to create more connections

        Furthermore, the sequence numbers Bitinex provides are per-connection
        so we need to bind our connection id to the message handler
        so we know to which connection the sequence number belongs.
        """
        pair_channels: List[Tuple[str, str]] = []
        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                if (pair[0] == 't') and (chan == FUNDING):
                    pair = 'f' + pair[1:]
                    # LOG.warning("%s: No %s for symbol %s => Skip subscription", self.id, chan, pair)
                    # continue
                pair_channels.append((pair, chan))
        # mix pair/channel combinations to avoid having most of the BTC & USD pairs within the same socket
        random.shuffle(pair_channels)
        # Bitfinex max is 25 per connection
        address = {}
        for options in split.list_by_max_items(pair_channels, 25):
            address[tuple(options)] = ws_endpoint
        LOG.info("%s: prepared %s WS connections", self.id, len(address))
        return address

    async def _ticker(self, pair: str, msg: dict, timestamp: float):
        if msg[1] == 'hb':
            return  # ignore heartbeats
        # bid, bid_size, ask, ask_size, daily_change, daily_change_percent,
        # last_price, volume, high, low
        bid, _, ask, _, _, _, _, _, _, _ = msg[1]
        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=bid,
                            ask=ask,
                            timestamp=timestamp,
                            receipt_timestamp=timestamp)

    async def _funding(self, pair: str, msg: dict, timestamp: float):
        async def _funding_update(funding: list, timestamp: float):
            order_id, ts, amount, price, period = funding
            await self.callback(FUNDING, feed=self.id,
                                symbol=pair,
                                side=SELL if amount < 0 else BUY,
                                amount=abs(amount),
                                price=Decimal(price),
                                order_id=order_id,
                                timestamp=timestamp_normalize(self.id, ts),
                                receipt_timestamp=timestamp,
                                period=period)

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

    async def _trades(self, pair: str, msg: dict, timestamp: float):
        async def _trade_update(trade: list, timestamp: float):
            order_id, ts, amount, price = trade
            await self.callback(TRADES, feed=self.id,
                                symbol=pair,
                                side=SELL if amount < 0 else BUY,
                                amount=abs(amount),
                                price=Decimal(price),
                                order_id=order_id,
                                timestamp=timestamp_normalize(self.id, ts),
                                receipt_timestamp=timestamp)

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

    async def _book(self, pair: str, l2_book: dict, msg: dict, timestamp: float):
        """For L2 book updates."""
        if not isinstance(msg[1], list):
            if msg[1] != 'hb':
                LOG.warning('%s: Unexpected book L2 msg %s', self.id, msg)
            return

        delta = {BID: [], ASK: []}

        if isinstance(msg[1][0], list):
            # snapshot so clear book
            forced = True
            l2_book[BID] = sd()
            l2_book[ASK] = sd()
            for update in msg[1]:
                price, _, amount = update
                price = Decimal(price)
                amount = Decimal(amount)

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = abs(amount)
                l2_book[side][price] = amount
        else:
            # book update
            forced = False
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
                l2_book[side][price] = amount
            else:
                # remove price level
                if price in l2_book[side]:
                    del l2_book[side][price]
                    delta[side].append((price, 0))

        await self.book_callback(l2_book, L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def _raw_book(self, pair: str, l3_book: dict, order_map: dict, msg: dict, timestamp: float):
        """For L3 book updates."""
        if not isinstance(msg[1], list):
            if msg[1] != 'hb':
                LOG.warning('%s: Unexpected book L3 msg %s', self.id, msg)
            return

        def add_to_book(side, price, order_id, amount):
            if price in l3_book[side]:
                l3_book[side][price][order_id] = amount
            else:
                l3_book[side][price] = {order_id: amount}

        def remove_from_book(side, order_id):
            price = order_map[side][order_id]['price']
            del l3_book[side][price][order_id]
            if len(l3_book[side][price]) == 0:
                del l3_book[side][price]

        delta = {BID: [], ASK: []}

        if isinstance(msg[1][0], list):
            # snapshot so clear orders
            forced = True
            order_map[BID] = {}
            order_map[ASK] = {}
            l3_book[BID] = sd()
            l3_book[ASK] = sd()

            for update in msg[1]:
                order_id, price, amount = update
                price = Decimal(price)
                amount = Decimal(amount)

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = - amount

                order_map[side][order_id] = {'price': price, 'amount': amount}
                add_to_book(side, price, order_id, amount)
        else:
            # book update
            forced = False
            order_id, price, amount = msg[1]
            price = Decimal(price)
            amount = Decimal(amount)

            if amount > 0:
                side = BID
            else:
                side = ASK
                amount = abs(amount)

            if price == 0:
                price = order_map[side][order_id]['price']
                remove_from_book(side, order_id)
                del order_map[side][order_id]
                delta[side].append((order_id, price, 0))
            else:
                if order_id in order_map[side]:
                    del_price = order_map[side][order_id]['price']
                    delta[side].append((order_id, del_price, 0))
                    # remove existing order before adding new one
                    delta[side].append((order_id, price, amount))
                    remove_from_book(side, order_id)
                else:
                    delta[side].append((order_id, price, amount))
                add_to_book(side, price, order_id, amount)
                order_map[side][order_id] = {'price': price, 'amount': amount}

        await self.book_callback(l3_book, L3_BOOK, pair, forced, delta, timestamp, timestamp)

    @staticmethod
    async def _do_nothing(msg: dict, timestamp: float):
        pass

    async def handle(self, data: bytes, timestamp: float, conn: AsyncConnection):
        assert isinstance(conn, WSAsyncConn)
        assert 'seq_no' in conn.ctx

        msg = json.loads(data, parse_float=Decimal)

        if isinstance(msg, list):
            chan_handler = conn.ctx['handlers'].get(msg[0])
            if chan_handler is None:
                LOG.warning('%s: Unregistered channel ID in message %s', conn.id, msg)
            else:
                seq_no = msg[-1]
                expected = conn.ctx['seq_no'] + 1
                if seq_no != expected:
                    LOG.warning('%s: missed message (sequence number) received %d, expected %d', conn.id, seq_no, expected)
                    raise MissingSequenceNumber
                conn.ctx['seq_no'] = seq_no
                await chan_handler(msg, timestamp)
        elif 'event' not in msg:
            LOG.warning('%s: Unexpected msg (missing event) from exchange: %s', conn.id, msg)
        elif msg['event'] == 'error':
            LOG.error('%s: Error from exchange: %s', conn.id, msg)
        elif msg['event'] in ('info', 'conf'):
            LOG.info('%s: %s from exchange: %s', conn.id, msg['event'], msg)
        elif 'chanId' in msg and 'symbol' in msg:
            self.register_channel_handler(msg, conn)
        else:
            LOG.warning('%s: Unexpected msg from exchange: %s', conn.id, msg)

    def register_channel_handler(self, msg: dict, conn: AsyncConnection):
        symbol = msg['symbol']
        is_funding = (symbol[0] == 'f')
        pair = symbol_exchange_to_std(symbol)

        if msg['channel'] == 'ticker':
            if is_funding:
                LOG.warning('%s %s: Ticker funding not implemented - set _do_nothing() for %s', conn.id, pair, msg)
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
                handler = partial(self._raw_book, pair, conn.ctx['L3'][pair], conn.ctx['order_map'][pair])
            elif is_funding:
                LOG.warning('%s %s: Book funding not implemented - set _do_nothing() for %s', conn.id, pair, msg)
                handler = self._do_nothing
            else:
                handler = partial(self._book, pair, conn.ctx['L2'][pair])
        else:
            LOG.warning('%s %s: Unexpected message %s', conn.id, pair, msg)
            return

        LOG.debug('%s: Register channel=%s pair=%s funding=%s %s -> %s()', conn.id, msg['channel'], pair, is_funding,
                  '='.join(list(msg.items())[-1]), handler.__name__ if hasattr(handler, '__name__') else handler.func.__name__)
        conn.ctx['handlers'][msg['chanId']] = handler

        LOG.warning("%s: Unexpected msg from exchange: %s", conn.id, msg)


    async def subscribe(self, conn: AsyncConnection):
        assert isinstance(conn, WSAsyncConn)
        assert 'opt' in conn.ctx
        assert isinstance(conn.ctx['opt'], Tuple)
        opt: Tuple[Tuple[str, str]] = conn.ctx['opt']
        LOG.info("%s: Subscribing to %s combinations: %s", conn.id, len(opt), opt)

        conn.ctx['L2'] = {}
        conn.ctx['L3'] = {}
        conn.ctx['order_map'] = defaultdict(dict)
        conn.ctx['handlers'] = {}  # maps a channel id (int) to a function
        conn.ctx['seq_no'] = 0

        await conn.send(json.dumps({
            'event': "conf",
            'flags': SEQ_ALL
        }))

        mapping = {FUNDING: 'trades'}

        for pair, chan in opt:
            message = {'event': 'subscribe',
                       'channel': mapping.get(chan, chan),
                       'symbol': pair}
            if 'book' in chan:
                parts = chan.split('-')
                if len(parts) != 1:
                    message['channel'] = 'book'
                    try:
                        message['prec'] = parts[1]
                        message['freq'] = parts[2]
                        message['len'] = parts[3]
                    except IndexError:
                        # any non specified params will be defaulted
                        pass
            LOG.info("%s: Send msg %r", conn.id, message)
            await conn.send(json.dumps(message))

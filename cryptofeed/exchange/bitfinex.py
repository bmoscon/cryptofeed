'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
from collections import defaultdict

from sortedcontainers import SortedDict as sd

from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.defines import TICKER, TRADES, L3_BOOK, BUY, SELL, BID, ASK, L2_BOOK, FUNDING, BITFINEX
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


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

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        if channels is not None and FUNDING in channels:
            if len(channels) > 1:
                raise ValueError("Funding channel must be in a separate feedhanlder on Bitfinex or you must use config")
        super().__init__('wss://api.bitfinex.com/ws/2', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}
        self.l3_book = {}
        '''
        channel map maps channel id (int) to a dict of
           symbol: channel's currency
           channel: channel name
           handler: the handler for this channel type
        '''
        self.channel_map = {}
        self.order_map = defaultdict(dict)
        self.seq_no = 0

    async def _ticker(self, msg: dict, timestamp: float):
        chan_id = msg[0]
        if msg[1] == 'hb':
            # ignore heartbeats
            pass
        else:
            # bid, bid_size, ask, ask_size, daily_change, daily_change_percent,
            # last_price, volume, high, low
            bid, _, ask, _, _, _, _, _, _, _ = msg[1]
            pair = self.channel_map[chan_id]['symbol']
            pair = pair_exchange_to_std(pair)
            await self.callback(TICKER, feed=self.id,
                                         pair=pair,
                                         bid=bid,
                                         ask=ask,
                                         timestamp=timestamp)

    async def _trades(self, msg: dict, timestamp: float):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        funding = pair[0] == 'f'
        pair = pair_exchange_to_std(pair)

        async def _trade_update(trade):
            if funding:
                order_id, ts, amount, price, period = trade
            else:
                order_id, ts, amount, price = trade
                period = None
            timestamp = timestamp_normalize(self.id, ts)
            side = SELL if amount < 0 else BUY
            amount = abs(amount)
            if period:
                await self.callback(FUNDING, feed=self.id,
                                              pair=pair,
                                              side=side,
                                              amount=amount,
                                              price=price,
                                              order_id=order_id,
                                              timestamp=timestamp,
                                              period=period)
            else:
                await self.callback(TRADES, feed=self.id,
                                             pair=pair,
                                             side=side,
                                             amount=amount,
                                             price=price,
                                             order_id=order_id,
                                             timestamp=timestamp)

        if isinstance(msg[1], list):
            # snapshot
            for trade_update in msg[1]:
                await _trade_update(trade_update)
        else:
            # update
            if msg[1] == 'te' or msg[1] == 'fte':
                await _trade_update(msg[2])
            elif msg[1] == 'tu' or msg[1] == 'ftu':
                # ignore trade updates
                pass
            elif msg[1] == 'hb':
                # ignore heartbeats
                pass
            else:
                LOG.warning("%s: Unexpected trade message %s", self.id, msg)

    async def _book(self, msg: dict, timestamp: float):
        """
        For L2 book updates
        """
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)
        delta = {BID: [], ASK: []}
        forced = False

        if isinstance(msg[1], list):
            if isinstance(msg[1][0], list):
                # snapshot so clear book
                self.l2_book[pair] = {BID: sd(), ASK: sd()}
                for update in msg[1]:
                    price, _, amount = update
                    price = Decimal(price)
                    amount = Decimal(amount)

                    if amount > 0:
                        side = BID
                    else:
                        side = ASK
                        amount = abs(amount)
                    self.l2_book[pair][side][price] = amount
                forced = True
            else:
                # book update
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
                    self.l2_book[pair][side][price] = amount
                else:
                    # remove price level
                    del self.l2_book[pair][side][price]
                    delta[side].append((price, 0))
        elif msg[1] == 'hb':
            pass
        else:
            LOG.warning("%s: Unexpected book msg %s", self.id, msg)

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp)

    async def _raw_book(self, msg: dict, timestamp: float):
        """
        For L3 book updates
        """
        def add_to_book(pair, side, price, order_id, amount):
            if price in self.l3_book[pair][side]:
                self.l3_book[pair][side][price][order_id] = amount
            else:
                self.l3_book[pair][side][price] = {order_id: amount}

        def remove_from_book(pair, side, order_id):
            price = self.order_map[pair][side][order_id]['price']
            del self.l3_book[pair][side][price][order_id]
            if len(self.l3_book[pair][side][price]) == 0:
                del self.l3_book[pair][side][price]

        delta = {BID: [], ASK: []}
        forced = False
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)

        if isinstance(msg[1], list):
            if isinstance(msg[1][0], list):
                # snapshot so clear orders
                self.order_map[pair] = {BID: {}, ASK: {}}
                self.l3_book[pair] = {BID: sd(), ASK: sd()}

                for update in msg[1]:
                    order_id, price, amount = update
                    price = Decimal(price)
                    amount = Decimal(amount)

                    if amount > 0:
                        side = BID
                    else:
                        side = ASK
                        amount = abs(amount)

                    self.order_map[pair][side][order_id] = {'price': price, 'amount': amount}
                    add_to_book(pair, side, price, order_id, amount)
                forced = True
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
                    remove_from_book(pair, side, order_id)
                    del self.order_map[pair][side][order_id]
                    delta[side].append((order_id, price, 0))
                else:
                    if order_id in self.order_map[pair][side]:
                        del_price = self.order_map[pair][side][order_id]['price']
                        delta[side].append((order_id, del_price, 0))
                        # remove existing order before adding new one
                        delta[side].append((order_id, price, amount))
                        remove_from_book(pair, side, order_id)
                    else:
                        delta[side].append((order_id, price, amount))
                    add_to_book(pair, side, price, order_id, amount)
                    self.order_map[pair][side][order_id] = {'price': price, 'amount': amount}

        elif msg[1] == 'hb':
            return
        else:
            LOG.warning("%s: Unexpected book msg %s", self.id, msg)
            return

        await self.book_callback(self.l3_book[pair], L3_BOOK, pair, forced, delta, timestamp)

    async def message_handler(self, msg: str, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg, list):
            chan_id = msg[0]
            if chan_id in self.channel_map:
                seq_no = msg[-1]
                if self.seq_no + 1 != seq_no:
                    LOG.warning("%s: missing sequence number. Received %d, expected %d", self.id, seq_no, self.seq_no + 1)
                    raise MissingSequenceNumber
                self.seq_no = seq_no

                await self.channel_map[chan_id]['handler'](msg, timestamp)
            else:
                LOG.warning("%s: Unexpected message on unregistered channel %s", self.id, msg)
        elif 'event' in msg and msg['event'] == 'error':
            LOG.error("%s: Error message from exchange: %s", self.id, msg['msg'])
        elif 'chanId' in msg and 'symbol' in msg:
            handler = None
            if msg['channel'] == 'ticker':
                handler = self._ticker
            elif msg['channel'] == 'trades':
                handler = self._trades
            elif msg['channel'] == 'book':
                if msg['prec'] == 'R0':
                    handler = self._raw_book
                else:
                    handler = self._book
            else:
                LOG.warning('%s: Invalid message type %s', self.id, msg)
                return

            self.channel_map[msg['chanId']] = {'symbol': msg['symbol'],
                                               'channel': msg['channel'],
                                               'handler': handler}

    async def subscribe(self, websocket):
        self.__reset()
        await websocket.send(json.dumps({
            'event': "conf",
            'flags': SEQ_ALL
        }))

        for channel in self.channels if not self.config else self.config:
            for pair in self.pairs if not self.config else self.config[channel]:
                message = {'event': 'subscribe',
                           'channel': channel,
                           'symbol': pair
                           }
                if 'book' in channel:
                    parts = channel.split('-')
                    if len(parts) != 1:
                        message['channel'] = 'book'
                        try:
                            message['prec'] = parts[1]
                            message['freq'] = parts[2]
                            message['len'] = parts[3]
                        except IndexError:
                            # any non specified params will be defaulted
                            pass
                await websocket.send(json.dumps(message))

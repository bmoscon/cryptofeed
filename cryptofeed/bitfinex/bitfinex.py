'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from decimal import Decimal
from collections import defaultdict
import time

from sortedcontainers import SortedDict as sd

from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.defines import TICKER, TRADES, L3_BOOK, BID, ASK, L2_BOOK, FUNDING, DEL, UPD
from cryptofeed.exchanges import BITFINEX
from cryptofeed.standards import pair_exchange_to_std


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
        super().__init__('wss://api.bitfinex.com/ws/2', pairs, channels, callbacks, **kwargs)
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


    async def _ticker(self, msg):
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
            await self.callbacks[TICKER](feed=self.id,
                                         pair=pair,
                                         bid=bid,
                                         ask=ask)

    async def _trades(self, msg):
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        funding = pair[0] == 'f'
        pair = pair_exchange_to_std(pair)

        async def _trade_update(trade):
            if funding:
                order_id, timestamp, amount, price, period = trade
            else:
                order_id, timestamp, amount, price = trade
                period = None
            if amount < 0:
                side = ASK
            else:
                side = BID
            amount = abs(amount)
            if period:
                await self.callbacks[FUNDING](feed=self.id,
                                              pair=pair,
                                              side=side,
                                              amount=amount,
                                              price=price,
                                              order_id=order_id,
                                              timestamp=timestamp,
                                              period=period)
            else:
                await self.callbacks[TRADES](feed=self.id,
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

    async def _book(self, msg):
        """
        For L2 book updates
        """
        timestamp = time.time() * 1000
        chan_id = msg[0]
        pair = self.channel_map[chan_id]['symbol']
        pair = pair_exchange_to_std(pair)
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
        forced = False

        if isinstance(msg[1], list):
            if isinstance(msg[1][0], list):
                # snapshot so clear book
                self.l2_book[pair] = {BID: sd(), ASK: sd()}
                for update in msg[1]:
                    price, _, amount = update
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

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = abs(amount)

                if count > 0:
                    # change at price level
                    delta[side] = {UPD: [(price, amount)]}
                    self.l2_book[pair][side][price] = amount
                else:
                    # remove price level
                    del self.l2_book[pair][side][price]
                    delta[side] = {DEL: [price]}
        elif msg[1] == 'hb':
            pass
        else:
            LOG.warning("%s: Unexpected book msg %s", self.id, msg)

        await self.book_callback(pair, L2_BOOK, forced, delta, timestamp)


    async def _raw_book(self, msg):
        """
        For L3 book updates
        """
        timestamp = time.time() * 1000
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

        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
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

                if amount > 0:
                    side = BID
                else:
                    side = ASK
                    amount = abs(amount)

                if price == 0:
                    price = self.order_map[pair][side][order_id]['price']
                    remove_from_book(pair, side, order_id)
                    del self.order_map[pair][side][order_id]
                    delta[side][DEL] = [(order_id, price)]
                else:
                    if order_id in self.order_map[pair][side]:
                        del_price = self.order_map[pair][side][order_id]['price']
                        delta[side][DEL] = [(order_id, del_price)]
                        # remove existing order before adding new one
                        delta[side][UPD] = [(order_id, price, amount)]
                        remove_from_book(pair, side, order_id)
                    else:
                        delta[side][UPD] = [(order_id, price, amount)]
                    add_to_book(pair, side, price, order_id, amount)
                    self.order_map[pair][side][order_id] = {'price': price, 'amount': amount}


        elif msg[1] == 'hb':
            return
        else:
            LOG.warning("%s: Unexpected book msg %s", self.id, msg)
            return

        await self.book_callback(pair, L3_BOOK, forced, delta, timestamp)

    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)

        if isinstance(msg, list):
            chan_id = msg[0]
            if chan_id in self.channel_map:
                seq_no = msg[-1]
                if self.seq_no + 1 != seq_no:
                    LOG.warning("%s: missing sequence number. Received %d, expected %d", self.id, seq_no, self.seq_no+1)
                    raise MissingSequenceNumber
                self.seq_no = seq_no

                await self.channel_map[chan_id]['handler'](msg)
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

        for channel in self.channels:
            for pair in self.pairs:
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

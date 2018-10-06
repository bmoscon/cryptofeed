'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import logging
from collections import defaultdict
from decimal import Decimal
from datetime import datetime as dt

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.exchanges import BITMEX
from cryptofeed.defines import L2_BOOK, BID, ASK, TRADES, UPD, DEL, FUNDING, L3_BOOK


LOG = logging.getLogger('feedhandler')


class Bitmex(Feed):
    id = BITMEX
    api = 'https://www.bitmex.com/api/v1/'

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://www.bitmex.com/realtime', pairs=None, channels=channels, callbacks=callbacks, **kwargs)
        active_pairs = self.get_active_symbols()
        for pair in pairs:
            if pair not in active_pairs:
                raise ValueError("{} is not active on BitMEX".format(pair))
        self.pairs = pairs
        self._reset()

    def _reset(self):
        self.partial_received = False
        self.order_id = {}
        for pair in self.pairs:
            self.l3_book[pair] = {BID: sd(), ASK: sd()}
            self.l2_book[pair] = {BID: sd(), ASK: sd()}
            self.order_id[pair] = defaultdict(dict)

    @staticmethod
    def get_symbol_info():
        return requests.get(Bitmex.api + 'instrument/').json()

    @staticmethod
    def get_active_symbols_info():
        return requests.get(Bitmex.api + 'instrument/active').json()

    @staticmethod
    def get_active_symbols():
        symbols = []
        for data in Bitmex.get_active_symbols_info():
            symbols.append(data['symbol'])
        return symbols

    async def _trade(self, msg):
        """
        trade msg example

        {
            'timestamp': '2018-05-19T12:25:26.632Z',
            'symbol': 'XBTUSD',
            'side': 'Buy',
            'size': 40,
            'price': 8335,
            'tickDirection': 'PlusTick',
            'trdMatchID': '5f4ecd49-f87f-41c0-06e3-4a9405b9cdde',
            'grossValue': 479920,
            'homeNotional': Decimal('0.0047992'),
            'foreignNotional': 40
        }
        """
        for data in msg['data']:
            await self.callbacks[TRADES](feed=self.id,
                                         pair=data['symbol'],
                                         side=BID if data['side'] == 'Buy' else ASK,
                                         amount=data['size'],
                                         price=data['price'],
                                         order_id=data['trdMatchID'],
                                         timestamp=data['timestamp'])

    async def _book(self, msg):
        """
        the Full bitmex book
        """
        timestamp = dt.utcnow()
        timestamp = timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        pair = None
        delta = {BID: defaultdict(list), ASK: defaultdict(list)}
        # if we reset the book, force a full update
        forced = False
        if not self.partial_received:
            # per bitmex documentation messages received before partial
            # should be discarded
            if msg['action'] != 'partial':
                return
            self.partial_received = True
            forced = True

        if msg['action'] == 'partial' or msg['action'] == 'insert':
            for data in msg['data']:
                side = BID if data['side'] == 'Buy' else ASK
                price = data['price']
                pair = data['symbol']
                size = data['size']
                order_id = data['id']

                if price in self.l3_book[pair][side]:
                    self.l3_book[pair][side][price][order_id] = size
                else:
                    self.l3_book[pair][side][price] = {order_id: size}
                self.order_id[pair][side][order_id] = (price, size)
                delta[side][UPD].append((order_id, price, size))
        elif msg['action'] == 'update':
            for data in msg['data']:
                side = BID if data['side'] == 'Buy' else ASK
                pair = data['symbol']
                update_size = data['size']
                order_id = data['id']

                price, _ = self.order_id[pair][side][order_id]

                self.l3_book[pair][side][price][order_id] = update_size
                self.order_id[pair][side][order_id] = (price, update_size)
                delta[side][UPD].append((order_id, price, update_size))
        elif msg['action'] == 'delete':
            for data in msg['data']:
                pair = data['symbol']
                side = BID if data['side'] == 'Buy' else ASK
                order_id = data['id']

                delete_price, _ = self.order_id[pair][side][order_id]
                del self.order_id[pair][side][order_id]
                del self.l3_book[pair][side][delete_price][order_id]

                if len(self.l3_book[pair][side][delete_price]) == 0:
                    del self.l3_book[pair][side][delete_price]

                delta[side][DEL].append((order_id, delete_price))

        else:
            LOG.warning("%s: Unexpected L3 Book message %s", self.id, msg)
            return

        await self.book_callback(pair, L3_BOOK, forced, delta, timestamp)

    async def _l2_book(self, msg):
        """
        top 10 orders from each side
        """
        timestamp = msg['data'][0]['timestamp']
        pair = None

        for update in msg['data']:
            pair = update['symbol']
            self.l2_book[pair][BID] = sd({
                Decimal(price): Decimal(amount)
                for price, amount in update['bids']
            })
            self.l2_book[pair][ASK] = sd({
                Decimal(price): Decimal(amount)
                for price, amount in update['asks']
            })

        await self.callbacks[L2_BOOK](feed=self.id, pair=pair, book=self.l2_book[pair], timestamp=timestamp)

    async def _funding(self, msg):
        """
        {'table': 'funding',
         'action': 'partial',
         'keys': ['timestamp', 'symbol'],
         'types': {
             'timestamp': 'timestamp',
             'symbol': 'symbol',
             'fundingInterval': 'timespan',
             'fundingRate': 'float',
             'fundingRateDaily': 'float'
            },
         'foreignKeys': {
             'symbol': 'instrument'
            },
         'attributes': {
             'timestamp': 'sorted',
             'symbol': 'grouped'
            },
         'filter': {'symbol': 'XBTUSD'},
         'data': [{
             'timestamp': '2018-08-21T20:00:00.000Z',
             'symbol': 'XBTUSD',
             'fundingInterval': '2000-01-01T08:00:00.000Z',
             'fundingRate': Decimal('-0.000561'),
             'fundingRateDaily': Decimal('-0.001683')
            }]
        }
        """
        for data in msg['data']:
            await self.callbacks[FUNDING](feed=self.id,
                                          pair=data['symbol'],
                                          timestamp=data['timestamp'],
                                          interval=data['fundingInterval'],
                                          rate=data['fundingRate'],
                                          rate_daily=data['fundingRateDaily']
                                         )


    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'info' in msg:
            LOG.info("%s - info message: %s", self.id, msg)
        elif 'subscribe' in msg:
            if not msg['success']:
                LOG.error("%s: subscribe failed: %s", self.id, msg)
        elif 'error' in msg:
            LOG.error("%s: Error message from exchange: %s", self.id, msg)
        else:
            if msg['table'] == 'trade':
                await self._trade(msg)
            elif msg['table'] == 'orderBookL2':
                await self._book(msg)
            elif msg['table'] == 'funding':
                await self._funding(msg)
            elif msg['table'] == 'orderBook10':
                await self._l2_book(msg)
            else:
                LOG.warning("%s: Unhandled message %s", self.id, msg)

    async def subscribe(self, websocket):
        self._reset()
        chans = []
        for channel in self.channels:
            for pair in self.pairs:
                chans.append("{}:{}".format(channel, pair))

        await websocket.send(json.dumps({"op": "subscribe",
                                         "args": chans}))

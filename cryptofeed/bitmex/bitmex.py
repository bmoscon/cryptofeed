'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json
import logging
from decimal import Decimal

import requests
from sortedcontainers import SortedDict as sd

from cryptofeed.feed import Feed
from cryptofeed.exchanges import BITMEX
from cryptofeed.standards import pair_exchange_to_std
from cryptofeed.defines import L2_BOOK, L3_BOOK, BID, ASK, TRADES, TICKER


LOG = logging.getLogger('feedhandler')


class Bitmex(Feed):
    id = BITMEX
    api = 'https://www.bitmex.com/api/v1/'

    def __init__(self, pairs=None, channels=None, callbacks=None):
        super().__init__('wss://www.bitmex.com/realtime', pairs=None, channels=channels, callbacks=callbacks)
        active_pairs = self.get_active_symbols()
        for pair in pairs:
            if pair not in active_pairs:
                raise ValueError("{} is not active on BitMEX".format(pair))
        self.pairs = pairs
        self.partial_received = False
        self.order_id = {}
        for pair in self.pairs:
            self.l2_book[pair] = {BID: sd(), ASK: sd()}
            self.order_id[pair] = {}

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
        for data in msg['data']:
            await self.callbacks[TRADES](feed=self.id,
                                         pair=data['symbol'],
                                         side=BID if data['side'] == 'Buy' else ASK,
                                         amount=data['size'],
                                         price=data['price'])
    
    async def _book(self, msg):
        pair = None
        if not self.partial_received:
            if msg['action'] != 'partial':
                return
            self.partial_received = True
        
        if msg['action'] == 'partial' or msg['action'] == 'insert':
            for data in msg['data']:
                side = BID if data['side'] == 'Buy' else ASK
                price = Decimal(data['price'])
                pair = data['symbol']
                size = Decimal(data['size'])
                self.l2_book[pair][side][price] = size
                self.order_id[pair][data['id']] = (price, size)
        elif msg['action'] == 'update':
            for data in msg['data']:
                side = BID if data['side'] == 'Buy' else ASK
                pair = data['symbol']
                update_size = Decimal(data['size'])
                price, _ = self.order_id[pair][data['id']]
                self.l2_book[pair][side][price] = update_size
                self.order_id[pair][data['id']] = (price, update_size)
        elif msg['action'] == 'delete':
            for data in msg['data']:
                pair = data['symbol']
                side = BID if data['side'] == 'Buy' else ASK
                delete_price, delete_size = self.order_id[pair][data['id']]
                del self.order_id[pair][data['id']]
                self.l2_book[pair][side][delete_price] -= delete_size
                if self.l2_book[pair][side][delete_price] == 0:
                    del self.l2_book[pair][side][delete_price]
        else:
            LOG.warning("{} - Unexpected L2 Book message {}".format(self.id, msg))
            return
        
        await self.callbacks[L2_BOOK](feed=self.id, pair=pair, book=self.l2_book[pair])


    async def message_handler(self, msg):
        msg = json.loads(msg, parse_float=Decimal)
        if 'info' in msg:
            LOG.info("%s - info message: %s", self.id, msg)
        elif 'subscribe' in msg:
            if not msg['success']:
                LOG.error("{} - subscribe failed: {}".format(self.id, msg))
        elif 'error' in msg:
            LOG.error("{} - Error message from exchange: {}".format(self.id, msg))
        else:
            if msg['table'] == 'trade':
                await self._trade(msg)
            elif msg['table'] == 'orderBookL2':
                await self._book(msg)
            else:
                LOG.warning("{} - Unhandled message {}".format(self.id, msg))

    async def subscribe(self, websocket):
        chans = []
        for channel in self.channels:
            for pair in self.pairs:
                chans.append("{}:{}".format(channel, pair))
    
        await websocket.send(json.dumps({"op": "subscribe", 
                                         "args": chans}))

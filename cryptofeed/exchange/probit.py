'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import logging
import time
from decimal import Decimal

import requests
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.defines import BID, ASK, BUY, PROBIT, L2_BOOK, L3_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import pair_exchange_to_std, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Probit(Feed):
    id = PROBIT

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__('wss://api.probit.com/api/exchange/v1/ws', pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _trades(self, msg: dict, timestamp: float):
        '''
        {
            "channel":"marketdata",
            "market_id":"ETH-BTC",
            "status":"ok","lag":0,
            "recent_trades":[
                {
                    "id":"ETH-BTC:4429182",
                    "price":"0.028229",
                    "quantity":"3.117",
                    "time":"2020-11-01T03:59:06.277Z",
                    "side":"buy","tick_direction":"down"
                },{
                    "id":"ETH-BTC:4429183",
                    "price":"0.028227",
                    "quantity":"1.793",
                    "time":"2020-11-01T03:59:14.528Z",
                    "side":"buy",
                    "tick_direction":"down"
                }
            ],"reset":true
        }

        {
            "channel":"marketdata",
            "market_id":"ETH-BTC",
            "status":"ok","lag":0,
            "recent_trades":[
                {
                    "id":"ETH-BTC:4429282",
                    "price":"0.028235",
                    "quantity":"2.203",
                    "time":"2020-11-01T04:22:15.117Z",
                    "side":"buy",
                    "tick_direction":"down"
                }
            ]
        }
        '''
        pair = pair_exchange_to_std(msg['market_id'])
        for update in msg['recent_trades']:
            price = Decimal(update['price'])
            quantity = Decimal(update['quantity'])
            side = BUY if update['side'] == 'buy' else SELL
            order_id = update['id']
            timestamp = timestamp_normalize(self.id, update['time'])
            await self.callback(TRADES, feed=self.id,
                                pair=pair,
                                side=side,
                                amount=quantity,
                                price=price,
                                order_id=order_id,
                                timestamp=timestamp,
                                receipt_timestamp=timestamp)

    async def _l2_update(self, msg: dict, timestamp: float):
        '''
        {
            "channel":"marketdata",
            "market_id":"ETH-BTC",
            "status":"ok",
            "lag":0,
            "order_books":[
            {
                "side":"buy",
                "price":"0.0165",
                "quantity":"0.47"
            },{
                "side":"buy",
                "price":"0",
                "quantity":"14656.177"
            },{
                "side":"sell",
                "price":"6400",
                "quantity":"0.001"
            }],
            "reset":true
        }
        {
            "channel":"marketdata",
            "market_id":"ETH-BTC",
            "status":"ok",
            "lag":0,
            "order_books":[
            {
                "side":"buy",
                "price":"0.0281",
                "quantity":"48.541"
            },{
                "side":"sell",
                "price":"0.0283",
                "quantity":"0"
            }]
        }
        '''
        pair = pair_exchange_to_std(msg['market_id'])

        is_snapshot = msg.get('reset', False)

        if is_snapshot:
            self.l2_book[pair] = {ASK: sd(), BID: sd()}

            for entry in msg["order_books"]:
                price = Decimal(entry['price'])
                quantity = Decimal(entry['quantity'])
                side = BID if entry['side'] == "buy" else ASK
                self.l2_book[pair][side][price] = quantity

            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, True, None, timestamp, timestamp)
        else:
            delta = {BID: [], ASK: []}

            for entry in msg["order_books"]:
                price = Decimal(entry['price'])
                quantity = Decimal(entry['quantity'])
                side = BID if entry['side'] == "buy" else ASK
                if quantity == 0:
                    if price in self.l2_book[pair][side]:
                        del self.l2_book[pair][side][price]
                    delta[side].append((price, 0))
                else:
                    self.l2_book[pair][side][price] = quantity
                    delta[side].append((price, quantity))

            await self.book_callback(self.l2_book[pair], L2_BOOK, pair, False, delta, timestamp, timestamp)

    async def message_handler(self, msg: str, timestamp: float):
        # print('incoming msg {}'.format(msg))
        msg = json.loads(msg, parse_float=Decimal)

        # Probit can send multiple type updates in one message
        if 'recent_trades' in msg:
            await self._trades(msg, timestamp)
        if 'order_books' in msg:
            await self._l2_update(msg, timestamp)

    async def subscribe(self, websocket):
        self.__reset()
        self.book_pairs = []

        if self.config:
            for chan in self.config:
                for pair in self.config[chan]:
                    await websocket.send(json.dumps({"type": "subscribe",
                                                     "channel": "marketdata",
                                                     "filter": [chan],
                                                     "interval": 100,
                                                     "market_id": pair,
                                                     }))
        else:
            for pair in self.pairs:
                await websocket.send(json.dumps({"type": "subscribe",
                                                 "channel": "marketdata",
                                                 "filter": list(self.channels),
                                                 "interval": 100,
                                                 "market_id": pair,
                                                 }))
                await asyncio.sleep(0.3)

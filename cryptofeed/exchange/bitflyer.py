'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, BITFLYER, TICKER, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize, symbol_exchange_to_std


LOG = logging.getLogger('feedhandler')


class Bitflyer(Feed):
    id = BITFLYER

    def __init__(self, **kwargs):
        super().__init__('wss://ws.lightstream.bitflyer.com/json-rpc', **kwargs)

    def __reset(self):
        self.l2_book = {}

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            "jsonrpc": "2.0",
            "method": "channelMessage",
            "params": {
                "channel":  "lightning_ticker_BTC_USD",
                "message": {
                    "product_code": "BTC_USD",
                    "state": "RUNNING",
                    "timestamp":"2020-12-25T21:16:19.3661298Z",
                    "tick_id": 703768,
                    "best_bid": 24228.97,
                    "best_ask": 24252.89,
                    "best_bid_size": 0.4006,
                    "best_ask_size": 0.4006,
                    "total_bid_depth": 64.73938803,
                    "total_ask_depth": 51.99613815,
                    "market_bid_size": 0.0,
                    "market_ask_size": 0.0,
                    "ltp": 24382.25,
                    "volume": 241.953371650000,
                    "volume_by_product": 241.953371650000
                }
            }
        }
        """
        pair = symbol_exchange_to_std(msg['params']['message']['product_code'])
        bid = msg['params']['message']['best_bid']
        ask = msg['params']['message']['best_ask']
        await self.callback(TICKER, feed=self.id,
                            symbol=pair,
                            bid=bid,
                            ask=ask,
                            timestamp=timestamp_normalize(self.id, msg['params']['message']['timestamp']),
                            receipt_timestamp=timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            "jsonrpc":"2.0",
            "method":"channelMessage",
            "params":{
                "channel":"lightning_executions_BTC_JPY",
                "message":[
                    {
                        "id":2084881071,
                        "side":"BUY",
                        "price":2509125.0,
                        "size":0.005,
                        "exec_date":"2020-12-25T21:36:22.8840579Z",
                        "buy_child_order_acceptance_id":"JRF20201225-213620-004123",
                        "sell_child_order_acceptance_id":"JRF20201225-213620-133314"
                    }
                ]
            }
        }
        """
        pair = msg['params']['channel'][21:]
        pair = symbol_exchange_to_std(pair)
        for update in msg['params']['message']:
            await self.callback(TRADES, feed=self.id,
                                order_id=update['id'],
                                symbol=pair,
                                side=BUY if update['side'] == 'BUY' else SELL,
                                amount=update['size'],
                                price=update['price'],
                                timestamp=timestamp_normalize(self.id, update['exec_date']),
                                receipt_timestamp=timestamp)

    async def _book(self, msg: dict, timestamp: float):
        """
        {
            "jsonrpc":"2.0",
            "method":"channelMessage",
            "params":{
                "channel":"lightning_board_BTC_JPY",
                "message":{
                    "mid_price":2534243.0,
                    "bids":[

                    ],
                    "asks":[
                        {
                        "price":2534500.0,
                        "size":0.0
                        },
                        {
                        "price":2536101.0,
                        "size":0.0
                        }
                    ]
                }
            }
        }
        """
        _, base, quote = msg['params']['channel'].rsplit('_', 2)
        pair = symbol_exchange_to_std(f'{base}_{quote}')
        snapshot = msg['params']['channel'].startswith('lightning_board_snapshot')
        forced = pair not in self.l2_book

        # Ignore deltas until a snapshot is received
        if pair not in self.l2_book and not snapshot:
            return

        if snapshot:
            if not forced:
                self.previous_book[pair] = self.l2_book[pair]
            self.l2_book[pair] = {BID: sd(), ASK: sd()}
            delta = None
        else:
            delta = {BID: [], ASK: []}
        data = msg['params']['message']

        for side, s in (('bids', BID), ('asks', ASK)):
            if snapshot:
                self.l2_book[pair][s] = {d['price']: d['size'] for d in data[side]}
            else:
                for entry in data[side]:
                    if entry['size'] == 0:
                        if entry['price'] in self.l2_book[pair][s]:
                            del self.l2_book[pair][s][entry['price']]
                            delta[s].append((entry['price'], Decimal(0.0)))
                    else:
                        self.l2_book[pair][s][entry['price']] = entry['size']
                        delta[s].append((entry['price'], entry['size']))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if msg['params']['channel'].startswith("lightning_ticker_"):
            await self._ticker(msg, timestamp)
        elif msg['params']['channel'].startswith('lightning_executions_'):
            await self._trade(msg, timestamp)
        elif msg['params']['channel'].startswith('lightning_board_'):
            await self._book(msg, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        for chan in set(self.channels or self.subscription):
            for pair in set(self.symbols or self.subscription[chan]):
                if chan.startswith('lightning_board'):
                    # need to subscribe to snapshots too if subscribed to L2_BOOKS
                    await conn.send(json.dumps({"method": "subscribe", "params": {"channel": f'lightning_board_snapshot_{pair}'}}))
                await conn.send(json.dumps({"method": "subscribe", "params": {"channel": chan.format(pair)}}))

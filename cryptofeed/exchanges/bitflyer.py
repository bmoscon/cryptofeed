'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, BITFLYER, FUTURES, TICKER, L2_BOOK, SELL, TRADES, FX
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import Ticker, Trade, OrderBook


LOG = logging.getLogger('feedhandler')


class Bitflyer(Feed):
    id = BITFLYER
    symbol_endpoint = endpoints = ['https://api.bitflyer.com/v1/getmarkets/eu', 'https://api.bitflyer.com/v1/getmarkets/usa', 'https://api.bitflyer.com/v1/getmarkets']
    websocket_channels = {
        L2_BOOK: 'lightning_board_{}',
        TRADES: 'lightning_executions_{}',
        TICKER: 'lightning_ticker_{}'
    }

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        for entry in data:
            for datum in entry:
                stype = datum['market_type'].lower()
                expiration = None

                if stype == FUTURES:
                    base, quote = datum['product_code'][:3], datum['product_code'][3:6]
                    expiration = datum['product_code'][6:]
                elif stype == FX:
                    _, base, quote = datum['product_code'].split("_")
                else:
                    base, quote = datum['product_code'].split("_")

                s = Symbol(base, quote, type=stype, expiry_date=expiration)
                ret[s.normalized] = datum['product_code']
                info['instrument_type'][s.normalized] = stype
        return ret, info

    def __init__(self, **kwargs):
        super().__init__('wss://ws.lightstream.bitflyer.com/json-rpc', **kwargs)

    def __reset(self):
        self._l2_book = {}

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
        pair = self.exchange_symbol_to_std_symbol(msg['params']['message']['product_code'])
        bid = msg['params']['message']['best_bid']
        ask = msg['params']['message']['best_ask']
        t = Ticker(self.id, pair, bid, ask, self.timestamp_normalize(msg['params']['message']['timestamp']), raw=msg)
        await self.callback(TICKER, t, timestamp)

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
        pair = self.exchange_symbol_to_std_symbol(msg['params']['channel'][21:])
        for update in msg['params']['message']:
            t = Trade(
                self.id,
                pair,
                BUY if update['side'] == 'BUY' else SELL,
                update['size'],
                update['price'],
                self.timestamp_normalize(update['exec_date']),
                raw=update
            )
            await self.callback(TRADES, t, timestamp)

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
        snapshot = msg['params']['channel'].startswith('lightning_board_snapshot')
        if snapshot:
            pair = msg['params']['channel'].split("lightning_board_snapshot")[1][1:]
        else:
            pair = msg['params']['channel'].split("lightning_board")[1][1:]
        pair = self.exchange_symbol_to_std_symbol(pair)

        # Ignore deltas until a snapshot is received
        if pair not in self._l2_book and not snapshot:
            return

        delta = None
        if snapshot:
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
        else:
            delta = {BID: [], ASK: []}

        data = msg['params']['message']
        for side in ('bids', 'asks'):
            s = BID if side == 'bids' else ASK
            if snapshot:
                self._l2_book[pair].book[side] = {d['price']: d['size'] for d in data[side]}
            else:
                for entry in data[side]:
                    if entry['size'] == 0:
                        if entry['price'] in self._l2_book[pair].book[side]:
                            del self._l2_book[pair].book[side][entry['price']]
                            delta[s].append((entry['price'], Decimal(0.0)))
                    else:
                        self._l2_book[pair].book[side][entry['price']] = entry['size']
                        delta[s].append((entry['price'], entry['size']))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg, delta=delta)

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

        for chan in self.subscription:
            for pair in self.subscription[chan]:
                if chan.startswith('lightning_board'):
                    # need to subscribe to snapshots too if subscribed to L2_BOOKS
                    await conn.write(json.dumps({"method": "subscribe", "params": {"channel": f'lightning_board_snapshot_{pair}'}}))
                await conn.write(json.dumps({"method": "subscribe", "params": {"channel": chan.format(pair)}}))

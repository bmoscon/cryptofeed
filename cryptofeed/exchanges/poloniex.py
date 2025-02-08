'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, POLONIEX, SELL, TRADES
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade


LOG = logging.getLogger('feedhandler')


class Poloniex(Feed):
    id = POLONIEX
    websocket_endpoints = [WebsocketEndpoint('wss://ws.poloniex.com/ws/public')]
    rest_endpoints = [RestEndpoint('https://api.poloniex.com', routes=Routes('/markets'))]
    websocket_channels = {
        L2_BOOK: 'book_lv2',
        TRADES: TRADES,
    }
    request_limit = 6

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}
        for entry in data:
            symbol = entry['symbol']
            std = symbol.replace("STR", "XLM")
            base, quote = std.split("_")
            s = Symbol(base, quote)
            ret[s.normalized] = symbol
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __reset(self):
        self._l2_book = {}
        self.seq_no = {}

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'channel': 'trades',
            'data': [{
                'symbol': 'BTC_USDT',
                'amount': '364.89973',
                'quantity': '0.017',
                'takerSide': 'sell',
                'createTime': 1661120814818,
                'price': '21464.69',
                'id': '60183607',
                'ts': 1661120814823
            }]
        }
        """
        price = Decimal(msg['data'][0]['price'])
        amount = Decimal(msg['data'][0]['amount'])
        t = Trade(
            msg['data'][0]['id'],
            self.exchange_symbol_to_std_symbol(msg['data'][0]['symbol']),
            SELL if msg['data'][0]['takerSide'] == 'sell' else BUY,
            amount,
            price,
            self.timestamp_normalize(msg['data'][0]['ts']),
            raw=msg
        )
        await self.callback(TRADES, t, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        data = msg['data'][0]
        pair = self.exchange_symbol_to_std_symbol(data['symbol'])

        if msg['action'] == 'snapshot':
            bids = {Decimal(price): Decimal(amount) for price, amount in data['bids']}
            asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, bids=bids, asks=asks)
            self.seq_no[pair] = data['id']
            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg, timestamp=self.timestamp_normalize(data['ts']))
        else:
            if data['lastId'] != self.seq_no[pair]:
                raise MissingSequenceNumber

            delta = {BID: [], ASK: []}
            for side in ('bids', 'asks'):
                for price, amount in data[side]:
                    price = Decimal(price)
                    amount = Decimal(amount)

                    if amount == 0:
                        del self._l2_book[pair].book[side][price]
                        delta[side[:-1]].append((price, 0))
                    else:
                        self._l2_book[pair].book[side][price] = amount
                        delta[side[:-1]].append((price, amount))
            self.seq_no[pair] = data['id']
            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(data['ts']), raw=msg, delta=delta)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        event = msg.get('event')
        if event == 'error':
            LOG.error("%s: Error from exchange: %s", self.id, msg)
            return
        elif event == 'subscribe':
            return

        channel = msg.get('channel')
        if channel == 'trades':
            await self._trade(msg, timestamp)
        elif channel == 'book_lv2':
            await self._book(msg, timestamp)
        else:
            LOG.warning('%s: Invalid message type %s', self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan, symbols in self.subscription.items():
            await conn.write(json.dumps({"event": "subscribe", "channel": [chan], "symbols": symbols}))

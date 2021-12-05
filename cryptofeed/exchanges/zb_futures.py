
'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from cryptofeed.symbols import Symbol
import logging
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, ZB_FUTURES, L2_BOOK, SELL, TRADES, PERPETUAL
from cryptofeed.feed import Feed
from cryptofeed.exchanges.mixins.zb_rest import ZbRestMixin
from cryptofeed.types import OrderBook, Trade

LOG = logging.getLogger('feedhandler')


class ZbFutures(Feed, ZbRestMixin):
    id = ZB_FUTURES
    symbol_endpoint = 'https://futures.zb.team/Server/api/v2/config/marketList'
    websocket_endpoint = 'wss://futures.zb.team/ws/public/v1'
    websocket_channels = {
        L2_BOOK: 'Depth',
        # TRADES: 'Trade',
    }
    request_limit = 10

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']:
            if entry['canTrade'] != True:
                continue
            stype = PERPETUAL
            s = Symbol(
                entry['sellerCurrencyName'].upper(),
                entry['buyerCurrencyName'].upper(),
                type=stype
            )
            ret[s.normalized] = entry['symbol']
            info['tick_size'][s.normalized] = entry['minAmount']  # zb does not provide tick size
            info['instrument_type'][s.normalized] = stype
        return ret, info

    def __reset(self):
        self._l2_book = {}
        self._last_server_time = 0

    async def _book(self, msg: dict, timestamp: float):
        symbol = msg['channel'].partition('.')[0]
        pair = self.exchange_symbol_to_std_symbol(symbol)
        delta = {BID: [], ASK: []}

        if 'type' not in msg:
            updated = False
            server_time = int(msg['data']['time'])
            for side, data in msg['data'].items():
                if side == 'bids':
                    side = BID
                elif side == 'asks':
                    side = ASK
                else:  # server time
                    continue
                for entry in data:
                    price = entry[0]
                    amount = entry[1]

                    if server_time < self._last_server_time:
                        continue

                    updated = True
                    self._last_server_time = server_time
                    delta[side].append((price, amount))

                    if amount == 0:
                        if price in self._l2_book[pair].book[side]:
                            del self._l2_book[pair].book[side][price]
                    else:
                        self._l2_book[pair].book[side][price] = amount
            if updated:
                await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, delta=delta, raw=msg)
        elif msg['type'] == 'Whole':
            # snapshot
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)
            self._last_server_time = int(msg['data']['time'])

            for side, data in msg['data'].items():
                if side == 'bids':
                    side = BID
                elif side == 'asks':
                    side = ASK
                else:  # server time
                    continue
                for entry in data:
                    size = entry[1]
                    if size > 0:
                        self._l2_book[pair].book[side][entry[0]] = size
            await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, delta=None, raw=msg)

#     async def _trade(self, msg: dict, timestamp: float):
#         """
#         update:
#         {
#            'type': 'channel_data',
#            'connection_id': '7b4abf85-f9eb-4f6e-82c0-5479ad5681e9',
#            'message_id': 18,
#            'id': 'DOGE-USD',
#            'channel': 'v3_trades',
#            'contents': {
#                'trades': [{
#                    'size': '390',
#                    'side': 'SELL',
#                    'price': '0.2334',
#                    'createdAt': datetime.datetime(2021, 6, 23, 22, 36, 34, 520000, tzinfo=datetime.timezone.utc)
#                 }]
#             }
#         }
# 
#         initial message:
#         {
#             'type': 'subscribed',
#             'connection_id': 'ccd8b74c-97b3-491d-a9fc-4a92a171296e',
#             'message_id': 4,
#             'channel': 'v3_trades',
#             'id': 'UNI-USD',
#             'contents': {
#                 'trades': [{
#                     'side': 'BUY',
#                     'size': '384.1',
#                     'price': '17.23',
#                     'createdAt': datetime.datetime(2021, 6, 23, 20, 28, 25, 465000, tzinfo=datetime.timezone.utc)
#                 },
#                 {
#                     'side': 'SELL',
#                     'size': '384.1',
#                     'price': '17.138',
#                     'createdAt': datetime.datetime(2021, 6, 23, 20, 22, 26, 466000, tzinfo=datetime.timezone.utc)},
#                }]
#             }
#         }
#         """
#         pair = self.exchange_symbol_to_std_symbol(msg['id'])
#         for trade in msg['contents']['trades']:
#             t = Trade(
#                 self.id,
#                 pair,
#                 BUY if trade['side'] == 'BUY' else SELL,
#                 Decimal(trade['size']),
#                 Decimal(trade['price']),
#                 self.timestamp_normalize(trade['createdAt']),
#                 raw=trade
#             )
#             await self.callback(TRADES, t, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'errorCode' not in msg:
            if msg['channel'].endswith('Depth'):
                await self._book(msg, timestamp)
            elif msg['channel'].endswith('Trade'):
                await self._trade(msg, timestamp)
            else:
                LOG.warning("%s: unexpected channel type received: %s", self.id, msg)
        else:
            LOG.error("%s: Websocket subscribe failed %s", self.id, msg['errorMsg'])

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()

        for chan, symbols in self.subscription.items():
            for symbol in symbols:
                msg = {"action": "subscribe", "channel": f"{symbol}.{chan}"}
                await conn.write(json.dumps(msg))


'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from decimal import Decimal
from typing import Dict, Tuple
from collections import defaultdict

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BID, BITGET, BUY, CANDLES, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import Ticker, Trade, Candle, OrderBook
from cryptofeed.util.time import timedelta_str_to_sec


LOG = logging.getLogger('feedhandler')


class Bitget(Feed):
    id = BITGET
    websocket_endpoints = [WebsocketEndpoint('wss://ws.bitget.com/spot/v1/stream')]
    rest_endpoints = [RestEndpoint('https://api.bitget.com', routes=Routes('/api/spot/v1/public/products'))]
    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '12h', '1d', '1w'}
    websocket_channels = {
        L2_BOOK: 'books',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'candle'
    }
    request_limit = 20

    @classmethod
    def timestamp_normalize(cls, ts: int) -> float:
        return ts / 1000

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']:
            """
            {
                "baseCoin":"ALPHA",
                "makerFeeRate":"0.001",
                "maxTradeAmount":"0",
                "minTradeAmount":"2",
                "priceScale":"4",
                "quantityScale":"4",
                "quoteCoin":"USDT",
                "status":"online",
                "symbol":"ALPHAUSDT_SPBL",
                "symbolName":"ALPHAUSDT",
                "takerFeeRate":"0.001"
            }
            """
            sym = Symbol(entry['baseCoin'], entry['quoteCoin'])
            info['instrument_type'][sym.normalized] = sym.type
            ret[sym.normalized] = entry['symbolName']
        return ret, info

    def __reset(self):
        self._l2_book = {}

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            'action': 'snapshot',
            'arg': {
                'instType': 'sp',
                'channel': 'ticker',
                'instId': 'BTCUSDT'
            },
            'data': [
                {
                    'instId': 'BTCUSDT',
                    'last': '46572.07',
                    'open24h': '46414.54',
                    'high24h': '46767.30',
                    'low24h': '46221.11',
                    'bestBid': '46556.590000',
                    'bestAsk': '46565.670000',
                    'baseVolume': '1927.0855',
                    'quoteVolume': '89120317.8812',
                    'ts': 1649013100029,
                    'labeId': 0
                }
            ]
        }
        """
        for entry in msg['data']:
            # sometimes snapshots do not have bids/asks in them
            if 'bestBid' not in entry or 'bestAsk' not in entry:
                continue
            t = Ticker(
                self.id,
                self.exchange_symbol_to_std_symbol(entry['instId']),
                Decimal(entry['bestBid']),
                Decimal(entry['bestAsk']),
                self.timestamp_normalize(entry['ts']),
                raw=entry
            )
            await self.callback(TICKER, t, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'action': 'update',
            'arg': {
                'instType': 'sp',
                'channel': 'trade',
                'instId': 'BTCUSDT'
            },
            'data': [
                ['1649014224602', '46464.51', '0.0023', 'sell']
            ]
        }
        """
        for entry in msg['data']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(msg['arg']['instId']),
                SELL if entry[3] == 'sell' else BUY,
                Decimal(entry[2]),
                Decimal(entry[1]),
                self.timestamp_normalize(int(entry[0])),
                raw=entry
            )
            await self.callback(TRADES, t, timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        '''
        {
            'action': 'update',
            'arg': {
                'instType': 'sp',
                'channel': 'candle1m',
                'instId': 'BTCUSDT'
            },
            'data': [['1649014920000', '46434.2', '46437.98', '46434.2', '46437.98', '0.9469']]
        }
        '''
        for entry in msg['data']:
            t = Candle(
                self.id,
                self.exchange_symbol_to_std_symbol(msg['arg']['instId']),
                self.timestamp_normalize(int(entry[0])),
                self.timestamp_normalize(int(entry[0])) + timedelta_str_to_sec(self.candle_interval),
                self.candle_interval,
                None,
                Decimal(entry[1]),
                Decimal(entry[4]),
                Decimal(entry[2]),
                Decimal(entry[3]),
                Decimal(entry[5]),
                None,
                self.timestamp_normalize(int(entry[0])),
                raw=entry
            )
            await self.callback(CANDLES, t, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        sym = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
        data = msg['data'][0]

        if msg['action'] == 'snapshot':
            '''
            {
                'action': 'snapshot',
                'arg': {
                    'instType': 'sp',
                    'channel': 'books',
                    'instId': 'BTCUSDT'
                },
                'data': [
                    {
                        'asks': [['46700.38', '0.0554'], ['46701.25', '0.0147'], ...
                        'bids': [['46686.68', '0.0032'], ['46684.75', '0.0161'], ...
                        'checksum': -393656186,
                        'ts': '1649021358917'
                    }
                ]
            }
            '''
            bids = {Decimal(price): Decimal(amount) for price, amount in data['bids']}
            asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}
            self._l2_book[sym] = OrderBook(self.id, sym, max_depth=self.max_depth, bids=bids, asks=asks)

            await self.book_callback(L2_BOOK, self._l2_book[sym], timestamp, checksum=data['checksum'], timestamp=self.timestamp_normalize(int(data['ts'])), raw=msg)

        else:
            '''
            {
                'action': 'update',
                'arg': {
                    'instType': 'sp',
                    'channel': 'books',
                    'instId': 'BTCUSDT'
                },
                'data': [
                    {
                        'asks': [['46701.25', '0'], ['46701.46', '0.0054'], ...
                        'bids': [['46687.67', '0.0531'], ['46686.22', '0'], ...
                        'checksum': -750266015,
                        'ts': '1649021359467'
                    }
                ]
            }
            '''
            delta = {BID: [], ASK: []}
            for side, key in ((BID, 'bids'), (ASK, 'asks')):
                for price, size in data[key]:
                    price = Decimal(price)
                    size = Decimal(size)
                    delta[side].append((price, size))

                    if size == 0:
                        del self._l2_book[sym].book[side][price]
                    else:
                        self._l2_book[sym].book[side][price] = size

            await self.book_callback(L2_BOOK, self._l2_book[sym], timestamp, delta=delta, checksum=data['checksum'], timestamp=self.timestamp_normalize(int(data['ts'])), raw=msg)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            # {'event': 'subscribe', 'arg': {'instType': 'sp', 'channel': 'ticker', 'instId': 'BTCUSDT'}}
            if msg['event'] == 'subscribe':
                return
            if msg['event'] == 'error':
                LOG.error('%s: Error from exchange: %s', conn.uuid, msg)
                return

        if msg['arg']['channel'] == 'books':
            await self._book(msg, timestamp)
        elif msg['arg']['channel'] == 'ticker':
            await self._ticker(msg, timestamp)
        elif msg['arg']['channel'] == 'trade':
            await self._trade(msg, timestamp)
        elif msg['arg']['channel'].startswith('candle'):
            await self._candle(msg, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        args = []

        interval = self.candle_interval
        if interval[-1] != 'm':
            interval[-1] = interval[-1].upper()

        for chan, symbols in conn.subscription.items():
            for s in symbols:
                d = {
                    'instType': 'SPBL' if self.is_authenticated_channel(self.exchange_channel_to_std(chan)) else 'SP',
                    'channel': chan if chan != 'candle' else 'candle' + interval,
                    'instId': s
                }
                args.append(d)

        await conn.write(json.dumps({"op": "subscribe", "args": args}))

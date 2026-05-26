'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


LMEX Spot Exchange Connector
API Docs:  https://lmex.io/apidoc/spot
WebSocket: wss://ws.lmex.io/ws/spot
REST:      https://api.lmex.io/spot/api/v3.2

Supported channels
  Public:        L2_BOOK, TRADES
  Authenticated: ORDER_INFO

WebSocket topics
  tradeHistoryApi:<SYMBOL>   - real-time trades
  notificationsApi           - private order events (auth required)

Order book delivery
  LMEX Spot does not expose a WebSocket order-book stream.  L2_BOOK is
  served by polling the REST endpoint
  GET /spot/api/v3.2/orderbook?symbol=<SYMBOL>&depth=200
  every `book_interval` seconds (default: 5).

Subscription message
  {"op": "subscribe", "args": ["tradeHistoryApi:BTC-USD"]}

Authentication
  Headers: request-api, request-nonce, request-sign
  Signature: HMAC-SHA384(secret, path + nonce + body)
'''
import hashlib
import hmac
import logging
import time
from collections import defaultdict
from decimal import Decimal
from typing import Dict, List, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BUY, CANCELLED, FAILED, FILLED, L2_BOOK, LMEX, OPEN, ORDER_INFO, PARTIAL, SELL, SUBMITTING, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, OrderInfo, Trade


LOG = logging.getLogger('feedhandler')

# LMEX order-status code -> cryptofeed status
_ORDER_STATUS = {
    2: OPEN,
    4: FILLED,
    5: PARTIAL,
    6: CANCELLED,
    7: CANCELLED,
    8: FAILED,
    9: OPEN,
    10: OPEN,
    15: FAILED,
    16: FAILED,
    17: FAILED,
    65: OPEN,
    85: SUBMITTING,
    88: OPEN,
}


class LMEX(Feed):
    '''
    LMEX Spot connector for cryptofeed.

    Channels
    --------
    L2_BOOK   - Full-depth L2 order book (REST-polled snapshot, refreshed
                every `book_interval` seconds; default 5 s)
    TRADES    - Real-time public trades (WebSocket)
    ORDER_INFO - Private order lifecycle events (WebSocket, auth required)
    '''

    id = LMEX

    websocket_endpoints = [
        WebsocketEndpoint('wss://ws.lmex.io/ws/spot', sandbox='wss://ws.test-api.lmex.io/ws/spot',
                          channel_filter=['tradeHistoryApi'],
                          options={'ping_interval': 10, 'ping_timeout': 30, 'max_size': None}),
        WebsocketEndpoint('wss://ws.lmex.io/ws/spot', sandbox='wss://ws.test-api.lmex.io/ws/spot',
                          channel_filter=['notificationsApi'], authentication=True,
                          options={'ping_interval': 10, 'ping_timeout': 30, 'max_size': None}),
    ]

    rest_endpoints = [
        RestEndpoint('https://api.lmex.io', sandbox='https://test-api.lmex.io',
                     routes=Routes('/spot/api/v3.2/market_summary',
                                   l2book='/spot/api/v3.2/orderbook'))
    ]

    websocket_channels = {
        L2_BOOK: 'orderBookApi',
        TRADES: 'tradeHistoryApi',
        ORDER_INFO: 'notificationsApi',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1_000.0

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for item in data:
            if not item.get('active', True):
                continue
            if item.get('futures', False):
                continue
            base = item.get('base')
            quote = item.get('quote')
            if not base or not quote:
                continue
            s = Symbol(base, quote)
            ret[s.normalized] = item['symbol']
            info['instrument_type'][s.normalized] = s.type
            if item.get('minPriceIncrement'):
                info['tick_size'][s.normalized] = Decimal(str(item['minPriceIncrement']))
            if item.get('minOrderSize'):
                info['lot_size'][s.normalized] = Decimal(str(item['minOrderSize']))

        return ret, info

    def __init__(self, book_interval: int = 5, **kwargs):
        self._book_interval = book_interval
        super().__init__(**kwargs)

    def connect(self) -> List:
        ret = super().connect()
        if L2_BOOK in self.subscription:
            for std_symbol in self.subscription[L2_BOOK]:
                exchange_symbol = self.std_symbol_to_exchange_symbol(std_symbol)
                url = self.rest_endpoints[0].route('l2book', self.sandbox) + f'?symbol={exchange_symbol}&depth=200'
                poll = HTTPPoll(url, self.id, delay=60, sleep=self._book_interval)
                ret.append((poll, self._book_subscribe, self._book_poll_handler, self.authenticate))
        return ret

    def _generate_signature(self, path: str, nonce: str, body: str = '') -> dict:
        message = path + nonce + body
        sig = hmac.new(self.key_secret.encode('utf-8'), message.encode('utf-8'), hashlib.sha384).hexdigest()
        return {'request-api': self.key_id, 'request-nonce': nonce, 'request-sign': sig}

    async def _ws_authentication(self, address: str, options: dict) -> Tuple[str, dict]:
        nonce = str(int(time.time() * 1_000))
        headers = self._generate_signature('/notificationsApi', nonce)
        options.setdefault('extra_headers', {}).update(headers)
        return address, options

    async def subscribe(self, conn: AsyncConnection):
        args = []
        for channel, symbols in conn.subscription.items():
            if channel == self.std_channel_to_exchange(L2_BOOK):
                continue  # L2_BOOK served via REST polling; skip WS subscription
            if channel == self.std_channel_to_exchange(ORDER_INFO):
                args.append(channel)
            else:
                for symbol in symbols:
                    args.append(f'{channel}:{symbol}')
        if args:
            await conn.write(json.dumps({'op': 'subscribe', 'args': args}))

    async def _book_subscribe(self, conn: HTTPPoll):
        pass

    async def _book_poll_handler(self, msg: str, conn: HTTPPoll, timestamp: float):
        '''
        REST orderbook response:
        {
            "symbol": "BTC-USD",
            "buyQuote":  [{"price": "77044.0", "size": "0.03214"}, ...],
            "sellQuote": [{"price": "77045.7", "size": "0.00365"}, ...],
            "timestamp": 1779800636554
        }
        Price and size values may be either strings or numbers depending on
        the endpoint version; Decimal(str(...)) handles both.
        '''
        data = json.loads(msg, parse_float=Decimal)
        symbol = self.exchange_symbol_to_std_symbol(data['symbol'])
        ts = self.timestamp_normalize(data['timestamp'])

        self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)
        for entry in data.get('buyQuote', []):
            price = Decimal(str(entry['price']))
            size = Decimal(str(entry['size']))
            if size > 0:
                self._l2_book[symbol].book.bids[price] = size
        for entry in data.get('sellQuote', []):
            price = Decimal(str(entry['price']))
            size = Decimal(str(entry['size']))
            if size > 0:
                self._l2_book[symbol].book.asks[price] = size

        await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, timestamp=ts, delta=None, raw=data)

    async def _trade(self, msg: dict, timestamp: float):
        '''
        {
            "topic": "tradeHistoryApi:BTC-USD",
            "data": [
                {
                    "symbol": "BTC-USD",
                    "side": "SELL",
                    "size": 0.0145,
                    "price": 76653.1,
                    "tradeId": 31626447,
                    "timestamp": 1779786372223
                }
            ]
        }
        '''
        for entry in msg.get('data', []):
            symbol = self.exchange_symbol_to_std_symbol(entry['symbol'])
            side = BUY if entry['side'] == 'BUY' else SELL
            price = Decimal(str(entry['price']))
            size = Decimal(str(entry['size']))
            ts = self.timestamp_normalize(entry['timestamp'])
            t = Trade(self.id, symbol, side, size, price, ts, id=str(entry.get('tradeId', '')), raw=entry)
            await self.callback(TRADES, t, timestamp)

    async def _order_info(self, msg: dict, timestamp: float):
        '''
        {
            "topic": "notificationsApi",
            "data": [
                {
                    "symbol": "BTC-USD",
                    "orderId": 987654321,
                    "clOrderId": "my-order-001",
                    "side": "BUY",
                    "price": 76500.0,
                    "size": 0.01,
                    "filledSize": 0.01,
                    "status": 4,
                    "timestamp": 1779786400000
                }
            ]
        }
        '''
        for entry in msg.get('data', []):
            status = _ORDER_STATUS.get(entry.get('status', 0), OPEN)
            symbol = self.exchange_symbol_to_std_symbol(entry['symbol'])
            side = BUY if entry['side'] == 'BUY' else SELL
            price = Decimal(str(entry['price'])) if entry.get('price') else None
            size = Decimal(str(entry['size']))
            filled = Decimal(str(entry.get('filledSize', 0)))
            remaining = size - filled
            ts = self.timestamp_normalize(entry['timestamp'])
            oi = OrderInfo(self.id, symbol, str(entry.get('orderId', '')), side, status, None, price, filled, remaining, ts, raw=entry)
            await self.callback(ORDER_INFO, oi, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        event = msg.get('event')
        if event == 'pong':
            return
        if event == 'subscribe':
            LOG.info('%s: Subscription confirmed: %s', self.id, msg.get('channel'))
            return
        if event:
            LOG.warning('%s: Unhandled event: %s', self.id, msg)
            return

        topic = msg.get('topic', '')
        if topic.startswith('tradeHistoryApi'):
            await self._trade(msg, timestamp)
        elif topic == 'notificationsApi':
            await self._order_info(msg, timestamp)
        else:
            LOG.warning('%s: Unknown topic: %s', self.id, topic)

'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.


LMEX Perpetual Futures Exchange Connector
API Docs:  https://lmex.io/apidoc/futures
WebSocket: wss://ws.lmex.io/ws/futures
REST:      https://api.lmex.io/futures/api/v2.3

Supported channels
  Public:        L2_BOOK, TRADES, FUNDING
  Authenticated: ORDER_INFO

WebSocket topics
  tradeHistoryApi:<SYMBOL>   - real-time trades (uses REST exchange symbol)
  notificationsApi           - private order events (auth required)

Trade message internals
  The futures WebSocket uses short internal codes for the `symbol` field
  inside trade data (e.g. "BTCPFC" for BTC-PERP).  The pattern for
  perpetuals is: base + "PFC"  →  "BTC" + "PFC" = "BTCPFC".

Order book delivery
  LMEX Futures does not expose a WebSocket order-book stream.  L2_BOOK is
  served by polling the REST endpoint
  GET /futures/api/v2.3/orderbook?symbol=<SYMBOL>&depth=200
  every `book_interval` seconds (default: 5).

Funding rate
  Polled via REST GET /futures/api/v2.3/market_summary every
  `funding_interval` seconds (default: 60).

Authentication
  Headers: request-api, request-nonce, request-sign
  Signature: HMAC-SHA384(secret, path + nonce + body)

Symbol notes
  REST symbol format:  BTC-PERP, ETH-PERP  (perpetuals only; dated futures
                        like BTC-260626 are excluded)
  Cryptofeed normalised: BTC-USDT-PERP, ETH-USDT-PERP
  WS internal code:    BTCPFC, ETHPFC  (base + "PFC")
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
from cryptofeed.defines import BUY, CANCELLED, FAILED, FILLED, FUNDING, L2_BOOK, LMEX_FUTURES, OPEN, ORDER_INFO, PARTIAL, PERPETUAL, SELL, SUBMITTING, TRADES
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.types import Funding, OrderBook, OrderInfo, Trade


LOG = logging.getLogger('feedhandler')

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


class LMEXFutures(Feed):
    '''
    LMEX Perpetual Futures connector for cryptofeed.

    Channels
    --------
    L2_BOOK   - Full-depth L2 order book (REST-polled snapshot, refreshed
                every `book_interval` seconds; default 5 s)
    TRADES    - Real-time public trades (WebSocket)
    FUNDING   - Funding rate (REST-polled every `funding_interval` s; default 60 s)
    ORDER_INFO - Private order lifecycle events (WebSocket, auth required)

    Symbol mapping
    --------------
    Only perpetuals are included (time-based / dated futures are excluded).
    LMEX REST symbol "BTC-PERP" maps to cryptofeed "BTC-USDT-PERP".
    The WebSocket internal code "BTCPFC" is derived as base + "PFC".
    '''

    id = LMEX_FUTURES

    websocket_endpoints = [
        WebsocketEndpoint('wss://ws.lmex.io/ws/futures', sandbox='wss://ws.test-api.lmex.io/ws/futures',
                          channel_filter=['tradeHistoryApi'],
                          options={'ping_interval': 10, 'ping_timeout': 30, 'max_size': None}),
        WebsocketEndpoint('wss://ws.lmex.io/ws/futures', sandbox='wss://ws.test-api.lmex.io/ws/futures',
                          channel_filter=['notificationsApi'], authentication=True,
                          options={'ping_interval': 10, 'ping_timeout': 30, 'max_size': None}),
    ]

    rest_endpoints = [
        RestEndpoint('https://api.lmex.io', sandbox='https://test-api.lmex.io',
                     routes=Routes('/futures/api/v2.3/market_summary',
                                   l2book='/futures/api/v2.3/orderbook'))
    ]

    websocket_channels = {
        L2_BOOK: 'orderBookApi',
        TRADES: 'tradeHistoryApi',
        ORDER_INFO: 'notificationsApi',
        FUNDING: FUNDING,
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
            # Skip dated/time-based futures (e.g. BTC-260626); only perpetuals
            if item.get('timeBasedContract', False):
                continue
            exchange_symbol = item['symbol']
            if not exchange_symbol.endswith('-PERP'):
                continue
            base = item.get('base') or exchange_symbol.split('-')[0]
            quote = item.get('quote', 'USDT')
            s = Symbol(base, quote, type=PERPETUAL)
            ret[s.normalized] = exchange_symbol
            info['instrument_type'][s.normalized] = s.type
            if item.get('minPriceIncrement'):
                info['tick_size'][s.normalized] = Decimal(str(item['minPriceIncrement']))
            if item.get('contractSize'):
                info['contract_size'][s.normalized] = Decimal(str(item['contractSize']))

        return ret, info

    def __init__(self, funding_interval: int = 60, book_interval: int = 5, **kwargs):
        self._funding_interval = funding_interval
        self._book_interval = book_interval
        super().__init__(**kwargs)

    def connect(self) -> List:
        ret = super().connect()
        if FUNDING in self.subscription:
            url = self.rest_endpoints[0].route('instruments', self.sandbox)
            poll = HTTPPoll(url, self.id, delay=60, sleep=self._funding_interval)
            ret.append((poll, self._funding_subscribe, self._funding_handler, self.authenticate))
        if L2_BOOK in self.subscription:
            for std_symbol in self.subscription[L2_BOOK]:
                exchange_symbol = self.std_symbol_to_exchange_symbol(std_symbol)
                url = self.rest_endpoints[0].route('l2book', self.sandbox) + f'?symbol={exchange_symbol}&depth=200'
                poll = HTTPPoll(url, self.id, delay=60, sleep=self._book_interval)
                ret.append((poll, self._book_subscribe, self._book_poll_handler, self.authenticate))
        return ret

    async def _funding_subscribe(self, conn: HTTPPoll):
        pass

    async def _funding_handler(self, msg: str, conn: HTTPPoll, timestamp: float):
        data = json.loads(msg, parse_float=Decimal)
        if not isinstance(data, list):
            data = [data]

        funding_symbols = {self.std_symbol_to_exchange_symbol(s) for s in self.subscription.get(FUNDING, [])}

        for item in data:
            exchange_symbol = item.get('symbol', '')
            if funding_symbols and exchange_symbol not in funding_symbols:
                continue
            if item.get('timeBasedContract', False):
                continue
            if not exchange_symbol.endswith('-PERP'):
                continue
            try:
                std_symbol = self.exchange_symbol_to_std_symbol(exchange_symbol)
            except Exception:
                continue
            rate = item.get('fundingRate')
            if rate is None:
                continue
            mark_price = item.get('last')
            ts = self.timestamp_normalize(item.get('timestamp', time.time() * 1000))
            f = Funding(self.id, std_symbol, Decimal(str(mark_price)) if mark_price is not None else None, Decimal(str(rate)), None, ts, raw=item)
            await self.callback(FUNDING, f, timestamp)

    async def _book_subscribe(self, conn: HTTPPoll):
        pass

    async def _book_poll_handler(self, msg: str, conn: HTTPPoll, timestamp: float):
        '''
        REST orderbook response:
        {
            "symbol": "BTC-PERP",
            "buyQuote":  [{"price": "77054.5", "size": "108350"}, ...],
            "sellQuote": [{"price": "77054.7", "size": "98250"}, ...],
            "timestamp": 1779800650027
        }
        Price and size values may be strings or numbers; Decimal(str(...)) handles both.
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
            if channel in (FUNDING, self.std_channel_to_exchange(L2_BOOK)):
                continue  # served via REST polling; skip WS subscription
            if channel == self.std_channel_to_exchange(ORDER_INFO):
                args.append(channel)
            else:
                for symbol in symbols:
                    args.append(f'{channel}:{symbol}')
        if args:
            await conn.write(json.dumps({'op': 'subscribe', 'args': args}))

    async def _trade(self, msg: dict, timestamp: float):
        '''
        The futures WebSocket sends a single "tradeHistoryApi" topic (no symbol
        suffix) with an internal symbol code in each data entry:

        {
            "topic": "tradeHistoryApi",
            "data": [
                {
                    "price": 77099.9,
                    "size": 6530,
                    "side": "SELL",
                    "symbol": "BTCPFC",
                    "tradeId": 35993384,
                    "timestamp": 1779800209269
                }
            ]
        }

        Internal code to exchange symbol conversion (perpetuals):
            BTCPFC  ->  BTC-PERP   (strip trailing "PFC", append "-PERP")
            ETHPFC  ->  ETH-PERP
            SOLPFC  ->  SOL-PERP
        '''
        for entry in msg.get('data', []):
            ws_code = entry.get('symbol', '')
            if ws_code.endswith('PFC'):
                exchange_symbol = ws_code[:-3] + '-PERP'
            else:
                LOG.warning('%s: unexpected futures WS symbol code: %s', self.id, ws_code)
                continue
            try:
                symbol = self.exchange_symbol_to_std_symbol(exchange_symbol)
            except Exception:
                LOG.warning('%s: cannot map futures symbol %s (WS code %s)', self.id, exchange_symbol, ws_code)
                continue
            side = BUY if entry['side'] == 'BUY' else SELL
            price = Decimal(str(entry['price']))
            size = Decimal(str(entry['size']))
            ts = self.timestamp_normalize(entry['timestamp'])
            t = Trade(self.id, symbol, side, size, price, ts, id=str(entry.get('tradeId', '')), raw=entry)
            await self.callback(TRADES, t, timestamp)

    async def _order_info(self, msg: dict, timestamp: float):
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
        if topic == 'tradeHistoryApi' or topic.startswith('tradeHistoryApi:'):
            await self._trade(msg, timestamp)
        elif topic == 'notificationsApi':
            await self._order_info(msg, timestamp)
        else:
            LOG.warning('%s: Unknown topic: %s', self.id, topic)

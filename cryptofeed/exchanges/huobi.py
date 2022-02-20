'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import base64
import asyncio
from datetime import datetime
import hashlib
import hmac
from urllib.parse import urlencode
from cryptofeed.symbols import Symbol
from cryptofeed.util.time import timedelta_str_to_sec
import logging
from typing import Dict, Tuple
import zlib
from decimal import Decimal

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BUY, CANDLES, FILLS, HUOBI, L2_BOOK, MAKER, ORDER_INFO, SELL, TAKER, TRADES, TICKER, OPEN, SUBMITTING, CLOSED, LIMIT, MARKET
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Candle, Ticker, OrderInfo, Fill

LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI
    is_auth = False
    rest_endpoints = [
        RestEndpoint('https://api.huobi.pro',
                     routes=Routes('/v1/common/symbols'))
    ]

    valid_candle_intervals = {
        '1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M', '1Y'
    }
    candle_interval_map = {
        '1m': '1min',
        '5m': '5min',
        '15m': '15min',
        '30m': '30min',
        '1h': '60min',
        '4h': '4hour',
        '1d': '1day',
        '1M': '1mon',
        '1w': '1week',
        '1Y': '1year'
    }
    websocket_channels = {
        L2_BOOK: 'depth.step0',
        TRADES: 'trade.detail',
        CANDLES: 'kline',
        TICKER: 'ticker',
        ORDER_INFO: 'orders',
        FILLS: 'trade.clearing'
    }
    websocket_endpoints = [
        WebsocketEndpoint('wss://api.huobi.pro/ws',
                          channel_filter=(websocket_channels[L2_BOOK],
                                          websocket_channels[TRADES],
                                          websocket_channels[TICKER],
                                          websocket_channels[CANDLES])),
        WebsocketEndpoint('wss://api.huobi.pro/ws/v2',
                          channel_filter=(websocket_channels[ORDER_INFO],
                                          websocket_channels[FILLS]))
    ]

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}

        for e in data['data']:
            if e['state'] == 'offline':
                continue
            base, quote = e['base-currency'].upper(
            ), e['quote-currency'].upper()
            s = Symbol(base, quote)

            ret[s.normalized] = e['symbol']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    def __reset(self):
        self._l2_book = {}

    async def _book(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1])
        data = msg['tick']
        if pair not in self._l2_book:
            self._l2_book[pair] = OrderBook(self.id,
                                            pair,
                                            max_depth=self.max_depth)

        self._l2_book[pair].book.bids = {
            Decimal(price): Decimal(amount)
            for price, amount in data['bids']
        }
        self._l2_book[pair].book.asks = {
            Decimal(price): Decimal(amount)
            for price, amount in data['asks']
        }

        await self.book_callback(L2_BOOK,
                                 self._l2_book[pair],
                                 timestamp,
                                 timestamp=self.timestamp_normalize(msg['ts']),
                                 raw=msg)

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {
            "ch":"market.btcusdt.ticker",
            "ts":1630982370526,
            "tick":{
                "open":51732,
                "high":52785.64,
                "low":51000,
                "close":52735.63,
                "amount":13259.24137056181,
                "vol":687640987.4125315,
                "count":448737,
                "bid":52732.88,
                "bidSize":0.036,
                "ask":52732.89,
                "askSize":0.583653,
                "lastPrice":52735.63,
                "lastSize":0.03
            }
        }
        """
        t = Ticker(self.id,
                   self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1]),
                   msg['tick']['bid'],
                   msg['tick']['ask'],
                   self.timestamp_normalize(msg['ts']),
                   raw=msg['tick'])
        await self.callback(TICKER, t, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'ch': 'market.adausdt.trade.detail',
            'ts': 1597792835344,
            'tick': {
                'id': 101801945127,
                'ts': 1597792835336,
                'data': [
                    {
                        'id': Decimal('10180194512782291967181675'),   <- per docs this is deprecated
                        'ts': 1597792835336,
                        'tradeId': 100341530602,
                        'amount': Decimal('0.1'),
                        'price': Decimal('0.137031'),
                        'direction': 'sell'
                    }
                ]
            }
        }
        """
        for trade in msg['tick']['data']:
            t = Trade(self.id,
                      self.exchange_symbol_to_std_symbol(
                          msg['ch'].split('.')[1]),
                      BUY if trade['direction'] == 'buy' else SELL,
                      Decimal(trade['amount']),
                      Decimal(trade['price']),
                      self.timestamp_normalize(trade['ts']),
                      id=str(trade['tradeId']),
                      raw=trade)
            await self.callback(TRADES, t, timestamp)

    async def _candles(self, msg: dict, symbol: str, interval: str,
                       timestamp: float):
        """
        {
            'ch': 'market.btcusdt.kline.1min',
            'ts': 1618700872863,
            'tick': {
                'id': 1618700820,
                'open': Decimal('60751.62'),
                'close': Decimal('60724.73'),
                'low': Decimal('60724.73'),
                'high': Decimal('60751.62'),
                'amount': Decimal('2.1990737759143966'),
                'vol': Decimal('133570.944386'),
                'count': 235}
            }
        }
        """
        interval = self.normalize_candle_interval[interval]
        start = int(msg['tick']['id'])
        end = start + timedelta_str_to_sec(interval) - 1
        c = Candle(self.id,
                   self.exchange_symbol_to_std_symbol(symbol),
                   start,
                   end,
                   interval,
                   msg['tick']['count'],
                   Decimal(msg['tick']['open']),
                   Decimal(msg['tick']['close']),
                   Decimal(msg['tick']['high']),
                   Decimal(msg['tick']['low']),
                   Decimal(msg['tick']['amount']),
                   None,
                   self.timestamp_normalize(msg['ts']),
                   raw=msg)
        await self.callback(CANDLES, c, timestamp)

    async def _fill(self, msg: dict, timestamp: float):
        """
        example message:
        {
            "ch": "trade.clearing#btcusdt#0",
            "data": {
                "eventType": "trade",
                "symbol": "btcusdt",
                "orderId": 99998888,
                "tradePrice": "9999.99",
                "tradeVolume": "0.96",
                "orderSide": "buy",
                "aggressor": true,
                "tradeId": 919219323232,
                "tradeTime": 998787897878,
                "transactFee": "19.88",
                "feeDeduct ": "0",
                "feeDeductType": "",
                "feeCurrency": "btc",
                "accountId": 9912791,
                "source": "spot-api",
                "orderPrice": "10000",
                "orderSize": "1",
                "clientOrderId": "a001",
                "orderCreateTime": 998787897878,
                "orderStatus": "partial-filled"
            }
        }
        """
        fill = msg['data']
        f = Fill(self.id,
                 self.exchange_symbol_to_std_symbol(fill['symbol']),
                 BUY if fill['orderSide'] == 'buy' else SELL,
                 Decimal(fill['tradeVolume']),
                 Decimal(fill['tradePrice']),
                 Decimal(fill['transactFee']),
                 str(fill['tradeId']),
                 str(fill['orderId']),
                 MARKET if fill['aggressor'] == True else LIMIT,
                 TAKER if fill['aggressor'] == True else MAKER,
                 self.timestamp_normalize(fill['tradeTime']),
                 account=self.subaccount,
                 raw=msg)
        await self.callback(FILLS, f, timestamp)

    async def _order(self, msg: dict, timestamp: float):
        """
        example message submitted:
        {
            "action":"push",
            "ch":"orders#btcusdt",
            "data":
            {
                "orderSize":"2.000000000000000000",
                "orderCreateTime":1583853365586,
                "accountld":992701,
                "orderPrice":"77.000000000000000000",
                "type":"sell-limit",
                "orderId":27163533,
                "clientOrderId":"abc123",
                "orderSource":"spot-api",
                "orderStatus":"submitted",
                "symbol":"btcusdt",
                "eventType":"creation"
            }
        }

        example message filled / partial:
        {
            "action":"push",
            "ch":"orders#btcusdt",
            "data":
            {
                "tradePrice":"76.000000000000000000",
                "tradeVolume":"1.013157894736842100",
                "tradeId":301,
                "tradeTime":1583854188883,
                "aggressor":true,
                "remainAmt":"0.000000000000000400000000000000000000",
                "execAmt":"2",
                "orderId":27163536,
                "type":"sell-limit",
                "clientOrderId":"abc123",
                "orderSource":"spot-api",
                "orderPrice":"15000",
                "orderSize":"0.01",
                "orderStatus":"filled",
                "symbol":"btcusdt",
                "eventType":"trade"
            }
        }
        """

        order = msg['data']
        if not order['eventType'] in ['creation', 'cancellation', 'trade']:
            LOG.debug(
                'wrong eventType (does not handle trigger orders yet): %s',
                msg)

        status = order['orderStatus']
        if status == 'new':
            status = SUBMITTING
        elif status == 'submitted':
            status = OPEN
        elif status == 'closed':
            status = CLOSED

        ts = (order.get('orderCreateTime') or order.get('tradeTime')
              or order.get('lastActTime'))
        oi = OrderInfo(
            self.id,
            self.exchange_symbol_to_std_symbol(order['symbol']),
            str(order['orderId']),
            BUY if 'buy' in order['type'] else SELL,
            status,
            LIMIT if 'limit' in order['type'] else MARKET,
            Decimal(order['orderPrice']) if 'orderPrice' in order else None,
            Decimal(order['orderSize']) if 'orderSize' in order else None,
            Decimal(order['remainAmt']) if 'remainAmt' in order else None,
            self.timestamp_normalize(ts) if ts else None,
            raw=msg)
        await self.callback(ORDER_INFO, oi, timestamp)

    def _auth(self, conn: AsyncConnection):
        method, host, path = 'GET', conn.conn.host, conn.conn.path
        ts = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S')

        params = {
            'accessKey': self.key_id,
            'signatureMethod': 'HmacSHA256',
            'signatureVersion': '2.1',
            'timestamp': ts
        }

        payload = '\n'.join([method, host, path, urlencode(params)])
        digest = hmac.new(self.key_secret.encode(), payload.encode(),
                          hashlib.sha256).digest()

        signature = base64.b64encode(digest).decode()
        msg = {
            'action': 'req',
            'ch': 'auth',
            'params': {
                'authType': 'api',
                **params,
                'signature': signature,
            }
        }

        return msg

    async def authenticate(self, conn: AsyncConnection):
        if self.requires_authentication and any(
                self.is_authenticated_channel(
                    self.exchange_channel_to_std(chan))
                for chan in conn.subscription):
            auth = self._auth(conn)
            LOG.debug(f"{conn.uuid}: Authenticating with message: {auth}")
            await conn.write(json.dumps(auth))

    async def message_handler(self, msg: str, conn: AsyncConnection,
                              timestamp: float):
        if not any(
                self.is_authenticated_channel(
                    self.exchange_channel_to_std(chan))
                for chan in conn.subscription):
            # unzip message if its from a compressed channel
            msg = zlib.decompress(msg, 16 + zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        LOG.debug(f"{conn.uuid}: Received message: {msg}")
        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        if 'ping' in msg:
            await conn.write(json.dumps({'pong': msg['ping']}))
        elif 'status' in msg and msg['status'] == 'ok':
            return
        elif 'action' in msg and msg['action'] == 'ping':
            msg['action'] = 'pong'
            await conn.write(json.dumps(msg))
        elif 'action' in msg and msg['action'] == 'sub':
            if msg['code'] != 200:
                LOG.warning("%s: Error with sub %s", self.id, msg)
            else:
                LOG.debug("%s: Successfully subscribed to %s", self.id,
                          msg['ch'])
        elif 'ch' in msg:
            if 'orders' in msg['ch']:
                await self._order(msg, timestamp)
            elif 'trade.clearing' in msg['ch']:
                await self._fill(msg, timestamp)
            elif 'trade' in msg['ch']:
                await self._trade(msg, timestamp)
            elif 'tick' in msg['ch']:
                await self._ticker(msg, timestamp)
            elif 'depth' in msg['ch']:
                await self._book(msg, timestamp)
            elif 'kline' in msg['ch']:
                _, symbol, _, interval = msg['ch'].split(".")
                await self._candles(msg, symbol, interval, timestamp)
            elif 'auth' in msg['ch']:
                LOG.debug(f"{self.id}: Successfully authenticated")
                self.is_auth = True
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        client_id = 0
        # wait for auth to be received before subscribing because otherwise we cannot sub to auth chans
        await asyncio.sleep(2)
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                client_id += 1
                normalized_chan = self.exchange_channel_to_std(chan)
                if self.is_authenticated_channel(
                        self.exchange_channel_to_std(chan)):
                    sub = f'{chan}#{pair}'
                    if normalized_chan == FILLS:
                        # mode fills only https://huobiapi.github.io/docs/spot/v1/en/#subscribe-trade-details-amp-order-cancellation-post-clearing
                        sub += '#0'
                    payload = {"action": "sub", "ch": sub}
                else:
                    payload = {
                        "sub":
                        f"market.{pair}.{chan}"
                        if normalized_chan != CANDLES else
                        f"market.{pair}.{chan}.{self.candle_interval_map[self.candle_interval]}",
                        "id":
                        client_id
                    }
                LOG.debug(f"{conn.uuid}: Subscribing chan: {payload}")
                await conn.write(json.dumps(payload))

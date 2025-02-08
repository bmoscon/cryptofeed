'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.symbols import Symbol
from cryptofeed.util.time import timedelta_str_to_sec
import logging
from typing import Dict, Tuple
import zlib
from decimal import Decimal

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BUY, CANDLES, HUOBI, L2_BOOK, SELL, TRADES, TICKER
from cryptofeed.feed import Feed
from cryptofeed.types import OrderBook, Trade, Candle, Ticker


LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI
    websocket_endpoints = [WebsocketEndpoint('wss://api.huobi.pro/ws')]
    rest_endpoints = [RestEndpoint('https://api.huobi.pro', routes=Routes('/v1/common/symbols'))]

    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M', '1Y'}
    candle_interval_map = {'1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min', '1h': '60min', '4h': '4hour', '1d': '1day', '1M': '1mon', '1w': '1week', '1Y': '1year'}
    websocket_channels = {
        L2_BOOK: 'depth.step0',
        TRADES: 'trade.detail',
        CANDLES: 'kline',
        TICKER: 'ticker'
    }

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
            base, quote = e['base-currency'].upper(), e['quote-currency'].upper()
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
            self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth)

        self._l2_book[pair].book.bids = {Decimal(price): Decimal(amount) for price, amount in data['bids']}
        self._l2_book[pair].book.asks = {Decimal(price): Decimal(amount) for price, amount in data['asks']}

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(msg['ts']), raw=msg)

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
        t = Ticker(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1]),
            msg['tick']['bid'],
            msg['tick']['ask'],
            self.timestamp_normalize(msg['ts']),
            raw=msg['tick']
        )
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
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1]),
                BUY if trade['direction'] == 'buy' else SELL,
                Decimal(trade['amount']),
                Decimal(trade['price']),
                self.timestamp_normalize(trade['ts']),
                id=str(trade['tradeId']),
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _candles(self, msg: dict, symbol: str, interval: str, timestamp: float):
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
        c = Candle(
            self.id,
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
            raw=msg
        )
        await self.callback(CANDLES, c, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        # unzip message
        msg = zlib.decompress(msg, 16 + zlib.MAX_WBITS)
        msg = json.loads(msg, parse_float=Decimal)

        # Huobi sends a ping evert 5 seconds and will disconnect us if we do not respond to it
        if 'ping' in msg:
            await conn.write(json.dumps({'pong': msg['ping']}))
        elif 'status' in msg and msg['status'] == 'ok':
            return
        elif 'ch' in msg:
            if 'trade' in msg['ch']:
                await self._trade(msg, timestamp)
            elif 'tick' in msg['ch']:
                await self._ticker(msg, timestamp)
            elif 'depth' in msg['ch']:
                await self._book(msg, timestamp)
            elif 'kline' in msg['ch']:
                _, symbol, _, interval = msg['ch'].split(".")
                await self._candles(msg, symbol, interval, timestamp)
            else:
                LOG.warning("%s: Invalid message type %s", self.id, msg)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        client_id = 0
        for chan in self.subscription:
            for pair in self.subscription[chan]:
                client_id += 1
                normalized_chan = self.exchange_channel_to_std(chan)
                await conn.write(json.dumps(
                    {
                        "sub": f"market.{pair}.{chan}" if normalized_chan != CANDLES else f"market.{pair}.{chan}.{self.candle_interval_map[self.candle_interval]}",
                        "id": client_id
                    }
                ))

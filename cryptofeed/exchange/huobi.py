'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.util.time import timedelta_str_to_sec
import logging
from typing import Dict, Tuple
import zlib
from decimal import Decimal

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BUY, CANDLES, HUOBI, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import normalize_channel, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Huobi(Feed):
    id = HUOBI
    symbol_endpoint = 'https://api.huobi.pro/v1/common/symbols'
    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M', '1Y'}

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        for e in data['data']:
            if e['state'] == 'offline':
                continue
            normalized = f"{e['base-currency'].upper()}{symbol_separator}{e['quote-currency'].upper()}"
            symbol = f"{e['base-currency']}{e['quote-currency']}"
            ret[normalized] = symbol
        return ret, {}

    def __init__(self, candle_interval='1m', **kwargs):
        super().__init__('wss://api.huobi.pro/ws', **kwargs)
        if candle_interval not in self.valid_candle_intervals:
            raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")
        lookup = {'1m': '1min', '5m': '5min', '15m': '15min', '30m': '30min', '1h': '60min', '4h': '4hour', '1d': '1day', '1M': '1mon', '1w': '1week', '1Y': '1year'}
        self.candle_interval = lookup[candle_interval]
        self.normalize_interval = {value: key for key, value in lookup.items()}
        self.__reset()

    def __reset(self):
        self.l2_book = {}

    async def _book(self, msg: dict, timestamp: float):
        pair = self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1])
        data = msg['tick']
        forced = pair not in self.l2_book

        update = {
            BID: sd({
                Decimal(price): Decimal(amount)
                for price, amount in data['bids']
            }),
            ASK: sd({
                Decimal(price): Decimal(amount)
                for price, amount in data['asks']
            })
        }

        if not forced:
            self.previous_book[pair] = self.l2_book[pair]
        self.l2_book[pair] = update

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, False, timestamp_normalize(self.id, msg['ts']), timestamp)

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
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(msg['ch'].split('.')[1]),
                                order_id=trade['tradeId'],
                                side=BUY if trade['direction'] == 'buy' else SELL,
                                amount=Decimal(trade['amount']),
                                price=Decimal(trade['price']),
                                timestamp=timestamp_normalize(self.id, trade['ts']),
                                receipt_timestamp=timestamp)

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
        interval = self.normalize_interval[interval]
        start = int(msg['tick']['id'])
        end = start + timedelta_str_to_sec(interval) - 1
        await self.callback(CANDLES,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(symbol),
                            timestamp=timestamp_normalize(self.id, msg['ts']),
                            receipt_timestamp=timestamp,
                            start=start,
                            stop=end,
                            interval=interval,
                            trades=msg['tick']['count'],
                            open_price=Decimal(msg['tick']['open']),
                            close_price=Decimal(msg['tick']['close']),
                            high_price=Decimal(msg['tick']['high']),
                            low_price=Decimal(msg['tick']['low']),
                            volume=Decimal(msg['tick']['amount']),
                            closed=None)

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
                normalized_chan = normalize_channel(self.id, chan)
                await conn.write(json.dumps(
                    {
                        "sub": f"market.{pair}.{chan}" if normalized_chan != CANDLES else f"market.{pair}.{chan}.{self.candle_interval}",
                        "id": client_id
                    }
                ))

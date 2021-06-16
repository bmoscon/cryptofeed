import asyncio
import base64
from cryptofeed.exceptions import MissingSequenceNumber
import logging
from typing import Dict, Tuple
import zlib
from decimal import Decimal

import requests
from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import BID, ASK, BITTREX, BUY, CANDLES, L2_BOOK, SELL, TICKER, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import normalize_channel, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Bittrex(Feed):
    id = BITTREX
    symbol_endpoint = 'https://api.bittrex.com/v3/markets'
    valid_candle_intervals = {'1m', '5m', '1h', '1d'}

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        return {f"{e['baseCurrencySymbol']}{symbol_separator}{e['quoteCurrencySymbol']}": e['symbol'] for e in data if e['status'] == 'ONLINE'}, {}

    def __init__(self, depth=500, candle_interval='1m', **kwargs):
        super().__init__('wss://socket-v3.bittrex.com/signalr/connect', **kwargs)
        r = requests.get('https://socket-v3.bittrex.com/signalr/negotiate', params={'connectionData': json.dumps([{'name': 'c3'}]), 'clientProtocol': 1.5})
        token = r.json()['ConnectionToken']
        url = requests.Request('GET', 'https://socket-v3.bittrex.com/signalr/connect', params={'transport': 'webSockets', 'connectionToken': token, 'connectionData': json.dumps([{"name": "c3"}]), 'clientProtocol': 1.5}).prepare().url
        url = url.replace('https://', 'wss://')
        self.address = url
        self.depth = depth
        if depth not in (1, 25, 500):
            if depth >= 500 or depth >= 25:
                self.depth = 500
            else:
                self.depth = 25
        if candle_interval not in self.valid_candle_intervals:
            raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")
        self.candle_interval = candle_interval

    def __reset(self):
        self.l2_book = {}
        self.seq_no = {}

    async def ticker(self, msg: dict, timestamp: float):
        """
        {
            'symbol': 'BTC-USDT',
            'lastTradeRate': '38904.35254113',
            'bidRate': '38868.52330647',
            'askRate': '38886.38815323'
        }
        """
        await self.callback(TICKER,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['symbol']),
                            bid=Decimal(msg['bidRate']),
                            ask=Decimal(msg['askRate']),
                            timestamp=timestamp,
                            receipt_timestamp=timestamp)

    async def book(self, msg: dict, timestamp: float):
        """
        {
            'marketSymbol': 'BTC-USDT',
            'depth': 500,
            'sequence': 6032818,
            'bidDeltas': [
                {
                    'quantity': '0',
                    'rate': '38926.13088302'
                },
                {
                    'quantity': '0.00213516',
                    'rate': '31881.73000000'
                }
            ],
            'askDeltas': [
                {
                    'quantity': '0.03106831',
                    'rate': '38989.50808432'
                },
                {
                    'quantity': '0.27954874',
                    'rate': '39013.57939993'
                },
                {
                    'quantity': '0',
                    'rate': '46667.67569819'
                }
            ]
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['marketSymbol'])
        seq_no = int(msg['sequence'])
        forced = False
        delta = {BID: [], ASK: []}

        if pair not in self.l2_book:
            forced = True
            await self._snapshot(pair, seq_no)
        else:
            if seq_no <= self.seq_no[pair]:
                return
            if seq_no != self.seq_no[pair] + 1:
                raise MissingSequenceNumber

            self.seq_no[pair] = seq_no
            for side, key in ((BID, 'bidDeltas'), (ASK, 'askDeltas')):
                for update in msg[key]:
                    price = Decimal(update['rate'])
                    size = Decimal(update['quantity'])
                    if size == 0:
                        delta[side].append((price, 0))
                        if price in self.l2_book[pair][side]:
                            del self.l2_book[pair][side][price]
                    else:
                        self.l2_book[pair][side][price] = size
                        delta[side].append((price, size))

        await self.book_callback(self.l2_book[pair], L2_BOOK, pair, forced, delta, timestamp, timestamp)

    async def _snapshot(self, symbol: str, sequence_number: int):
        while True:
            ret, headers = await self.http_conn.read(f'https://api.bittrex.com/v3/markets/{symbol}/orderbook?depth={self.depth}', return_headers=True)
            seq = int(headers['Sequence'])
            if seq >= sequence_number:
                break
            await asyncio.sleep(1.0)

        self.seq_no[symbol] = seq
        data = json.loads(ret, parse_float=Decimal)
        self.l2_book[symbol] = {BID: {}, ASK: {}}
        for side, entries in data.items():
            self.l2_book[symbol][side] = sd({Decimal(e['rate']): Decimal(e['quantity']) for e in entries})

    async def trades(self, msg: dict, timestamp: float):
        """
        {
            'deltas': [
                {
                    'id': '8e7f693b-6504-4cb7-9484-835435b147f9',
                    'executedAt': datetime.datetime(2021, 6, 13, 22, 38, 11, 80000, tzinfo=datetime.timezone.utc),
                    'quantity': '0.00693216',
                    'rate': '38808.83000000',
                    'takerSide': 'BUY'
                }
            ],
            'sequence': 204392,
            'marketSymbol': 'BTC-USD'
        }
        """
        pair = self.exchange_symbol_to_std_symbol(msg['marketSymbol'])
        for trade in msg['deltas']:
            await self.callback(TRADES,
                                feed=self.id,
                                order_id=trade['id'],
                                symbol=pair,
                                side=BUY if trade['takerSide'] == 'BUY' else SELL,
                                amount=Decimal(trade['quantity']),
                                price=Decimal(trade['rate']),
                                timestamp=timestamp_normalize(self.id, trade['executedAt']),
                                receipt_timestamp=timestamp)

    async def candle(self, msg: dict, timestamp: float):
        """
        {
            'sequence': 134514,
            'marketSymbol': 'BTC-USDT',
            'interval': 'MINUTE_1',
            'delta': {
                'startsAt': datetime.datetime(2021, 6, 14, 1, 12, tzinfo=datetime.timezone.utc),
                'open': '39023.31434847',
                'high': '39023.31434847',
                'low': '39023.31434847',
                'close': '39023.31434847',
                'volume': '0.05944473',
                'quoteVolume': '2319.73038514'
            },
            'candleType': 'TRADE'
        }
        """
        start = timestamp_normalize(self.id, msg['delta']['startsAt'])
        offset = 0
        if self.candle_interval == '1m':
            offset = 60
        elif self.candle_interval == '5m':
            offset = 300
        elif self.candle_interval == '1h':
            offset = 3600
        elif self.candle_interval == '1d':
            offset = 86400
        end = start + offset

        await self.callback(CANDLES,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['marketSymbol']),
                            timestamp=timestamp,
                            receipt_timestamp=timestamp,
                            start=start,
                            stop=end,
                            interval=self.candle_interval,
                            trades=None,
                            open_price=Decimal(msg['delta']['open']),
                            close_price=Decimal(msg['delta']['close']),
                            high_price=Decimal(msg['delta']['high']),
                            low_price=Decimal(msg['delta']['low']),
                            volume=Decimal(msg['delta']['volume']),
                            closed=None)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg)
        if 'M' in msg and len(msg['M']) > 0:
            for update in msg['M']:
                if update['M'] == 'orderBook':
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.book(data, timestamp)
                elif update['M'] == 'trade':
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.trades(data, timestamp)
                elif update['M'] == 'ticker':
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.ticker(data, timestamp)
                elif update['M'] == 'candle':
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.candle(data, timestamp)
                else:
                    LOG.warning("%s: Invalid message type %s", self.id, msg)
        elif 'E' in msg:
            LOG.error("%s: Error from exchange %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        # H: Hub, M: Message, A: Args, I: Internal ID
        # For more signalR info see:
        # https://blog.3d-logic.com/2015/03/29/signalr-on-the-wire-an-informal-description-of-the-signalr-protocol/
        # http://blogs.microsoft.co.il/applisec/2014/03/12/signalr-message-format/
        for chan in self.subscription:
            channel = normalize_channel(self.id, chan)
            i = 1
            for symbol in self.subscription[chan]:
                if channel == L2_BOOK:
                    msg = {'A': ([chan.format(symbol, self.depth)],), 'H': 'c3', 'I': i, 'M': 'Subscribe'}
                elif channel in (TRADES, TICKER):
                    msg = {'A': ([chan.format(symbol)],), 'H': 'c3', 'I': i, 'M': 'Subscribe'}
                elif channel == CANDLES:
                    interval = None
                    if self.candle_interval == '1m':
                        interval = 'MINUTE_1'
                    elif self.candle_interval == '5m':
                        interval = 'MINUTE_5'
                    elif self.candle_interval == '1h':
                        interval = 'HOUR_1'
                    elif self.candle_interval == '1d':
                        interval = 'DAY_1'
                    msg = {'A': ([chan.format(symbol, interval)],), 'H': 'c3', 'I': i, 'M': 'Subscribe'}
                else:
                    LOG.error("%s: invalid subscription for channel %s", channel)
                await conn.write(json.dumps(msg))
                i += 1

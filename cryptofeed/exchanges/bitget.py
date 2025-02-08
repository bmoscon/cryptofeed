'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import base64
import hmac
import logging
from decimal import Decimal
from time import time
from typing import Dict, List, Tuple, Union
from collections import defaultdict

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import ASK, BALANCES, BID, BITGET, BUY, CANCELLED, CANDLES, FILLED, L2_BOOK, LONG, OPEN, ORDER_INFO, PARTIAL, PERPETUAL, POSITIONS, SELL, SHORT, SPOT, TICKER, TRADES
from cryptofeed.exceptions import BadChecksum
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol, str_to_symbol
from cryptofeed.types import Ticker, Trade, Candle, OrderBook, Balance, Position, OrderInfo
from cryptofeed.util.time import timedelta_str_to_sec


LOG = logging.getLogger('feedhandler')


class Bitget(Feed):
    id = BITGET
    websocket_endpoints = [
        WebsocketEndpoint('wss://ws.bitget.com/spot/v1/stream', instrument_filter=('TYPE', (SPOT,))),
        WebsocketEndpoint('wss://ws.bitget.com/mix/v1/stream', instrument_filter=('TYPE', (PERPETUAL,))),
    ]
    rest_endpoints = [
        RestEndpoint('https://api.bitget.com', instrument_filter=('TYPE', (SPOT,)), routes=Routes('/api/spot/v1/public/products')),
        RestEndpoint('https://api.bitget.com', instrument_filter=('TYPE', (PERPETUAL,)), routes=Routes(['/api/mix/v1/market/contracts?productType=umcbl', '/api/mix/v1/market/contracts?productType=dmcbl'])),
    ]

    valid_candle_intervals = {'1m', '5m', '15m', '30m', '1h', '4h', '12h', '1d', '1w'}
    websocket_channels = {
        L2_BOOK: 'books',
        TRADES: 'trade',
        TICKER: 'ticker',
        CANDLES: 'candle',
        ORDER_INFO: 'orders',
        BALANCES: 'account',
        POSITIONS: 'positions'
    }
    request_limit = 20

    @classmethod
    def timestamp_normalize(cls, ts: int) -> float:
        return ts / 1000

    @classmethod
    def _parse_symbol_data(cls, data: Union[List, Dict]) -> Tuple[Dict, Dict]:
        """
        contract types

        umcbl	USDT Unified Contract
        dmcbl	Quanto Swap Contract
        sumcbl	USDT Unified Contract Analog disk (naming makes no sense, but these are basically testnet coins)
        sdmcbl	Quanto Swap Contract Analog disk (naming makes no sense, but these are basically testnet coins)
        """
        ret = {}
        info = defaultdict(dict)

        if isinstance(data, dict):
            data = [data]
        for d in data:
            for entry in d['data']:
                """
                Spot

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
                if "symbolName" in entry:
                    sym = Symbol(entry['baseCoin'], entry['quoteCoin'])
                    ret[sym.normalized] = entry['symbolName']
                else:
                    sym = Symbol(entry['baseCoin'], entry['quoteCoin'], type=PERPETUAL)
                    ret[sym.normalized] = entry['symbol']
                info['instrument_type'][sym.normalized] = sym.type
                info['is_quanto'][sym.normalized] = 'dmcbl' in entry['symbol'].lower()

        return ret, info

    def __reset(self, conn: AsyncConnection):
        if self.std_channel_to_exchange(L2_BOOK) in conn.subscription:
            for pair in conn.subscription[self.std_channel_to_exchange(L2_BOOK)]:
                std_pair = self.exchange_symbol_to_std_symbol(pair)

                if std_pair in self._l2_book:
                    del self._l2_book[std_pair]

    async def _ticker(self, msg: dict, timestamp: float, symbol: str):
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
        key = 'ts'
        if msg['arg']['instType'] == 'mc':
            key = 'systemTime'

        for entry in msg['data']:
            # sometimes snapshots do not have bids/asks in them
            if 'bestBid' not in entry or 'bestAsk' not in entry:
                continue
            t = Ticker(
                self.id,
                symbol,
                Decimal(entry['bestBid']),
                Decimal(entry['bestAsk']),
                self.timestamp_normalize(entry[key]),
                raw=entry
            )
            await self.callback(TICKER, t, timestamp)

    async def _trade(self, msg: dict, timestamp: float, symbol: str):
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
                symbol,
                SELL if entry[3] == 'sell' else BUY,
                Decimal(entry[2]),
                Decimal(entry[1]),
                self.timestamp_normalize(int(entry[0])),
                raw=entry
            )
            await self.callback(TRADES, t, timestamp)

    async def _candle(self, msg: dict, timestamp: float, symbol: str):
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
                symbol,
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

    async def _book(self, msg: dict, timestamp: float, symbol: str):
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
            self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth, bids=bids, asks=asks, checksum_format=self.id)

            if self.checksum_validation and self._l2_book[symbol].book.checksum() != (data['checksum'] & 0xFFFFFFFF):
                raise BadChecksum
            await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, checksum=data['checksum'], timestamp=self.timestamp_normalize(int(data['ts'])), raw=msg)

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
                        del self._l2_book[symbol].book[side][price]
                    else:
                        self._l2_book[symbol].book[side][price] = size

            if self.checksum_validation and self._l2_book[symbol].book.checksum() != (data['checksum'] & 0xFFFFFFFF):
                raise BadChecksum
            await self.book_callback(L2_BOOK, self._l2_book[symbol], timestamp, delta=delta, checksum=data['checksum'], timestamp=self.timestamp_normalize(int(data['ts'])), raw=msg)

    async def _account(self, msg: dict, symbol: str, timestamp: float):
        '''
        spot

        {
            'action': 'snapshot',
            'arg': {
                'instType': 'spbl',
                'channel': 'account',
                'instId': 'BTCUSDT_SPBL'
            },
            'data': []
        }

        futures

        {
            'action': 'snapshot',
            'arg': {
                'instType': 'dmcbl',
                'channel': 'account',
                'instId': 'BTCUSD_DMCBL'
            },
            'data': [{
                'marginCoin': 'BTC',
                'locked': '0.00000000',
                'available': '0.00000000',
                'maxOpenPosAvailable': '0.00000000',
                'maxTransferOut': '0.00000000',
                'equity': '0.00000000',
                'usdtEquity': '0.000000000000'
            },
            {
                'marginCoin': 'ETH',
                'locked': '0.00000000',
                'available': '0.00000000',
                'maxOpenPosAvailable': '0.00000000',
                'maxTransferOut': '0.00000000',
                'equity': '0.00000000',
                'usdtEquity': '0.000000000000'
            }]
        }
        '''
        for entry in msg['data']:
            b = Balance(
                self.id,
                symbol,
                Decimal(entry['available']),
                Decimal(entry['locked']),
                raw=entry
            )
            await self.callback(BALANCES, b, timestamp)

    async def _positions(self, msg: dict, symbol: str, timestamp: float):
        '''
        {
            'action': 'snapshot',
            'arg': {
                'instType': 'sumcbl',
                'channel': 'positions',
                'instId': 'SBTCSUSDT_SUMCBL'
            },
            'data': [
                {
                    'posId': '900434465966956544',
                    'instId': 'SBTCSUSDT_SUMCBL',
                    'instName': 'SBTCSUSDT',
                    'marginCoin': 'SUSDT',
                    'margin': '103.2987',
                    'marginMode': 'crossed',
                    'holdSide': 'long',
                    'holdMode': 'double_hold',
                    'total': '0.05',
                    'available': '0.05',
                    'locked': '0',
                    'averageOpenPrice': '41319.5',
                    'leverage': 20,
                    'achievedProfits': '0',
                    'upl': '0.518',
                    'uplRate': '0.005',
                    'liqPx': '0',
                    'keepMarginRate': '0.004',
                    'marginRate': '0.022209875738',
                    'cTime': '1650406226626',
                    'uTime': '1650406613064'
                }
            ]
        }
        '''
        # exchange, symbol, position, entry_price, side, unrealised_pnl, timestamp, raw=None):
        for entry in msg['data']:
            p = Position(
                self.id,
                symbol,
                Decimal(entry['total']),
                Decimal(entry['averageOpenPrice']),
                LONG if entry['holdSide'] == 'long' else SHORT,
                Decimal(entry['upl']),
                self.timestamp_normalize(int(entry['uTime'])),
                raw=entry
            )
            await self.callback(POSITIONS, p, timestamp)

    def _status(self, status: str) -> str:
        if status == 'new':
            return OPEN
        if status == 'partial-fill':
            return PARTIAL
        if status == 'full-fill':
            return FILLED
        if status == 'cancelled':
            return CANCELLED
        return status

    async def _order(self, msg: dict, symbol: str, timestamp: float):
        '''
        {
            'action': 'snapshot',
            'arg': {
                'instType': 'sumcbl',
                'channel': 'orders',
                'instId': 'default'
            }, 'data': [
                {
                    'accFillSz': '0',
                    'cTime': 1650407316266,
                    'clOrdId': '900439036248367104',
                    'force': 'normal',
                    'instId': 'SBTCSUSDT_SUMCBL',
                    'lever': '20',
                    'notionalUsd': '2065.175',
                    'ordId': '900439036185452544',
                    'ordType': 'market',
                    'orderFee': [
                        {'feeCcy': 'SUSDT', 'fee': '0'
                    }],
                    'posSide': 'long',
                    'px': '0',
                    'side': 'buy',
                    'status': 'new',
                    'sz': '0.05',
                    'tdMode': 'cross',
                    'tgtCcy': 'SUSDT',
                    'uTime': 1650407316266
                }
            ]
        }


        filled:

        {
            'action': 'snapshot',
            'arg': {
                'instType': 'sumcbl',
                'channel': 'orders',
                'instId': 'default'
            },
            'data': [{
                'accFillSz': '0.1',
                'avgPx': '41400',
                'cTime': 1650408010067,
                'clOrdId': '900441946260676608',
                'execType': 'T',
                'fillFee': '-2.484',
                'fillFeeCcy': 'SUSDT',
                'fillNotionalUsd': '4140',
                'fillPx': '41400',
                'fillSz': '0.1',
                'fillTime': '1650408010163',
                'force': 'normal',
                'instId': 'SBTCSUSDT_SUMCBL',
                'lever': '20',
                'notionalUsd': '4139.95',
                'ordId': '900441946180984832',
                'ordType': 'market',
                'orderFee': [{'feeCcy': 'SUSDT', 'fee': '-2.484'}],
                'pnl': '0',
                'posSide': 'long',
                'px': '0',
                'side': 'buy',
                'status': 'full-fill',
                'sz': '0.1',
                'tdMode': 'cross',
                'tgtCcy': 'SUSDT',
                'tradeId': '900441946663366657',
                'uTime': 1650408010163
            }]
        }
        '''
        for entry in msg['data']:

            o = OrderInfo(
                self.id,
                self.exchange_symbol_to_std_symbol(entry['instId']),
                entry['ordId'],
                entry['side'],
                self._status(entry['status']),
                entry['ordType'],
                Decimal(entry['px'] if 'fillPx' not in entry else entry['fillPx']),
                Decimal(entry['sz']),
                Decimal(entry['sz']) - Decimal(entry['accFillSz']),
                self.timestamp_normalize(int(entry['uTime'])),
                client_order_id=entry['clOrdId'],
                raw=entry
            )
            await self.callback(ORDER_INFO, o, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            # {'event': 'subscribe', 'arg': {'instType': 'sp', 'channel': 'ticker', 'instId': 'BTCUSDT'}}
            if msg['event'] == 'login' and msg['code'] == 0:
                LOG.info("%s: Authenticated successfully", conn.uuid)
                return
            if msg['event'] == 'subscribe':
                return
            if msg['event'] == 'error':
                LOG.error('%s: Error from exchange: %s', conn.uuid, msg)
                return

        symbol = msg['arg']['instId']
        if symbol != 'default':
            if msg['arg']['instType'] == 'mc':
                if symbol.endswith('T'):
                    symbol = self.exchange_symbol_to_std_symbol(symbol + "_UMCBL")
                else:
                    symbol = self.exchange_symbol_to_std_symbol(symbol + "_DMCBL")
            elif msg['arg']['instType'] in {'dmcbl', 'umcbl'}:
                symbol = self.exchange_symbol_to_std_symbol(symbol)
            elif msg['arg']['instType'] == 'sp':
                symbol = self.exchange_symbol_to_std_symbol(symbol)
            else:
                # SPBL
                symbol = self.exchange_symbol_to_std_symbol(symbol.split("_")[0])

        if msg['arg']['channel'] == 'books':
            await self._book(msg, timestamp, symbol)
        elif msg['arg']['channel'] == 'ticker':
            await self._ticker(msg, timestamp, symbol)
        elif msg['arg']['channel'] == 'trade':
            await self._trade(msg, timestamp, symbol)
        elif msg['arg']['channel'].startswith('candle'):
            await self._candle(msg, timestamp, symbol)
        elif msg['arg']['channel'].startswith('account'):
            await self._account(msg, symbol, timestamp)
        elif msg['arg']['channel'].startswith('orders'):
            await self._order(msg, symbol, timestamp)
        elif msg['arg']['channel'].startswith('positions'):
            await self._positions(msg, symbol, timestamp)
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def _login(self, conn: AsyncConnection):
        LOG.debug("%s: Attempting authentication", conn.uuid)
        timestamp = int(time())
        msg = f"{timestamp}GET/user/verify"
        msg = hmac.new(bytes(self.key_secret, encoding='utf8'), bytes(msg, encoding='utf-8'), digestmod='sha256')
        sign = str(base64.b64encode(msg.digest()), 'utf8')
        await conn.write(json.dumps({
            "op": "login",
            "args": [{
                "apiKey": self.key_id,
                "passphrase": self.key_passphrase,
                "timestamp": timestamp,
                "sign": sign
            }]
        }))

    async def subscribe(self, conn: AsyncConnection):
        if self.key_id and self.key_passphrase and self.key_secret:
            await self._login(conn)
        self.__reset(conn)
        args = []

        interval = self.candle_interval
        if interval[-1] != 'm':
            interval = f"{interval[:-1]}{interval[-1].upper()}"

        for chan, symbols in conn.subscription.items():
            for s in symbols:
                sym = str_to_symbol(self.exchange_symbol_to_std_symbol(s))
                if sym.type == SPOT:
                    if chan == 'positions':  # positions not applicable on spot
                        continue
                    if self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                        itype = 'spbl'
                        s += '_SPBL'
                    else:
                        itype = 'SP'
                else:
                    if self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                        itype = s.split('_')[-1]
                        if chan == 'orders':
                            s = 'default'  # currently only supports 'default' for order channel on futures
                    else:
                        itype = 'MC'
                        s = s.split("_")[0]

                d = {
                    'instType': itype,
                    'channel': chan if chan != 'candle' else 'candle' + interval,
                    'instId': s
                }
                args.append(d)

        await conn.write(json.dumps({"op": "subscribe", "args": args}))

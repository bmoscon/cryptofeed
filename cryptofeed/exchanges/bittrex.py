import asyncio
import base64
import hashlib
import hmac
import logging
import time
from typing import Dict, Tuple
import uuid
import zlib
from decimal import Decimal

import requests
from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BALANCES, BID, ASK, BITTREX, BUY, CANDLES, L2_BOOK, SELL, TICKER, TRADES, ORDER_INFO, CLOSED, OPEN, SUBMITTING, MARKET, LIMIT
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exceptions import MissingSequenceNumber
from cryptofeed.types import OrderBook, Trade, Ticker, Candle, OrderInfo, Balance


LOG = logging.getLogger('feedhandler')


class Bittrex(Feed):
    id = BITTREX
    websocket_endpoints = [WebsocketEndpoint('wss://www.bitmex.com/realtime', authentication=True)]
    rest_endpoints = [RestEndpoint('https://api.bittrex.com', routes=Routes('/v3/markets', l2book='/v3/markets/{}/orderbook?depth={}'))]

    valid_candle_intervals = {'1m', '5m', '1h', '1d'}
    valid_depths = [1, 25, 500]
    websocket_channels = {
        L2_BOOK: 'orderbook_{}_{}',
        TRADES: 'trade_{}',
        TICKER: 'ticker_{}',
        CANDLES: 'candle_{}_{}',
        ORDER_INFO: 'order',
        BALANCES: 'balance'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        info = {'instrument_type': {}}
        ret = {}
        for e in data:
            if e['status'] != 'ONLINE':
                continue
            s = Symbol(e['baseCurrencySymbol'], e['quoteCurrencySymbol'])
            ret[s.normalized] = e['symbol']
            info['instrument_type'][s.normalized] = s.type
        return ret, info

    async def _ws_authentication(self, address: str, options: dict) -> Tuple[str, dict]:
        # Technically this isnt authentication, its the negotiation step for SignalR that
        # we are performing here since this method is called right before connecting
        r = self.http_sync.read('https://socket-v3.bittrex.com/signalr/negotiate', params={'connectionData': json.dumps([{'name': 'c3'}]), 'clientProtocol': 1.5}, json=True)
        token = r['ConnectionToken']
        url = requests.Request('GET', 'https://socket-v3.bittrex.com/signalr/connect', params={'transport': 'webSockets', 'connectionToken': token, 'connectionData': json.dumps([{"name": "c3"}]), 'clientProtocol': 1.5}).prepare().url
        return url.replace('https://', 'wss://'), options

    def __reset(self):
        self._l2_book = {}
        self.seq_no = {}

    def __depth(self):
        depth = self.valid_depths[-1]
        if self.max_depth:
            if 25 <= self.max_depth >= 500:
                depth = 500
            else:
                depth = 25
        return depth

    async def ticker(self, msg: dict, timestamp: float):
        """
        {
            'symbol': 'BTC-USDT',
            'lastTradeRate': '38904.35254113',
            'bidRate': '38868.52330647',
            'askRate': '38886.38815323'
        }
        """
        t = Ticker(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['symbol']),
            Decimal(msg['bidRate']),
            Decimal(msg['askRate']),
            None,
            raw=msg
        )
        await self.callback(TICKER, t, timestamp)

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
        delta = {BID: [], ASK: []}

        if pair not in self._l2_book:
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
                        if price in self._l2_book[pair].book[side]:
                            del self._l2_book[pair].book[side][price]
                    else:
                        self._l2_book[pair].book[side][price] = size
                        delta[side].append((price, size))

        await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, raw=msg, sequence_number=seq_no, delta=delta)

    async def _snapshot(self, symbol: str, sequence_number: int):
        while True:
            ret, headers = await self.http_conn.read(self.rest_endpoints[0].route('l2book', self.sandbox).format(symbol, self.__depth()), return_headers=True)
            seq = int(headers['Sequence'])
            if seq >= sequence_number:
                break
            await asyncio.sleep(1.0)

        self.seq_no[symbol] = seq
        data = json.loads(ret, parse_float=Decimal)
        self._l2_book[symbol] = OrderBook(self.id, symbol, max_depth=self.max_depth)
        for side, entries in data.items():
            self._l2_book[symbol].book[side] = {Decimal(e['rate']): Decimal(e['quantity']) for e in entries}
        await self.book_callback(L2_BOOK, self._l2_book[symbol], time.time(), raw=data, sequence_number=seq)

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
            t = Trade(
                self.id,
                pair,
                BUY if trade['takerSide'] == 'BUY' else SELL,
                Decimal(trade['quantity']),
                Decimal(trade['rate']),
                self.timestamp_normalize(trade['executedAt']),
                id=trade['id'],
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

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
        start = self.timestamp_normalize(msg['delta']['startsAt'])
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

        c = Candle(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['marketSymbol']),
            start,
            end,
            self.candle_interval,
            None,
            Decimal(msg['delta']['open']),
            Decimal(msg['delta']['close']),
            Decimal(msg['delta']['high']),
            Decimal(msg['delta']['low']),
            Decimal(msg['delta']['volume']),
            None,
            None,
            raw=msg
        )
        await self.callback(CANDLES, c, timestamp)

    async def order(self, msg: dict, timestamp: float):
        """
        example message:
        {
            "accountId": "17f2b2e3-ff86-4357-a76b-34124ee30274",
            "sequence": 22606,
            "delta": {
                "id": "01fa3794-10cf-4897-bc47-c96f15135f34",
                "marketSymbol": "VLX-USDT",
                "direction": "SELL",
                "type": "LIMIT",
                "quantity": "50.00000000",
                "limit": "0.049000000000",
                "timeInForce": "GOOD_TIL_CANCELLED",
                "fillQuantity": "0.00000000",
                "commission": "0.00000000",
                "proceeds": "0.00000000",
                "status": "OPEN",
                "createdAt": "2022-08-05T15:04:16.02Z",
                "updatedAt": "2022-08-05T15:04:16.02Z"
            }
        }
        """
        order = msg['delta']
        status = order['status']
        if status == 'new':
            status = SUBMITTING
            # There was no observation made, that there are more than "OPEN" and "CLOSED". Needs Support clarification with BITTREX.
        elif status == 'OPEN':
            status = OPEN
        elif status == 'CLOSED':
            status = CLOSED

        remainingSize = Decimal(order['quantity']) - Decimal(order['fillQuantity'])

        oi = OrderInfo(
            self.id,
            self.exchange_symbol_to_std_symbol(order['marketSymbol']),
            str(order['id']),
            BUY if order['direction'].lower() == 'buy' else SELL,
            status,
            LIMIT if order['type'].lower() == 'limit' else MARKET,
            Decimal(order['limit']) if 'limit' in order else None,
            Decimal(order['fillQuantity']),  # the filled Size
            remainingSize,  # the remaining Size
            timestamp=str(order['createdAt']),
            client_order_id=order['clientOrderId'] if 'clientOrderId' in order else None,
            # account=self.subaccount,
            raw=msg
        )
        await self.callback(ORDER_INFO, oi, timestamp)

    async def balance(self, msg: dict, timestamp: float):
        """
            {
                "accountId": "17f42de3-ff86-4357-a76b-34124ee30c63",
                "sequence": 33119,
                "delta": {
                    "currencySymbol": "VLX",
                    "total": "636.02206857",
                    "available": "0.00000000",
                    "updatedAt": "2022-08-05T13:46:31.73Z"
                }
            }
        """
        delta = msg["delta"]
        available = Decimal(delta["available"])
        locked = Decimal(delta["total"]) - available
        bal = Balance(
            self.id,
            delta['currencySymbol'],
            available,
            locked,
            raw=msg
        )
        await self.callback(BALANCES, bal, timestamp)

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg)
        if 'R' in msg and ('Success') in msg['R']:
            LOG.info(f"Authenticated for private subscriptions: {msg['R']['Success']}")
        elif 'M' in msg and len(msg['M']) > 0:
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
                elif update['M'] == 'order':
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.order(data, timestamp)
                elif update['M'] == 'balance':
                    for message in update['A']:
                        data = json.loads(zlib.decompress(base64.b64decode(message), -zlib.MAX_WBITS).decode(), parse_float=Decimal)
                        await self.balance(data, timestamp)
                elif update['M'] == 'authenticationExpiring':
                    # WARNING : BITTREX: Invalid message type {'C': 'd-942EDED9-B,0|Bjh,1|Bji,3|Bjj,0|Bjk,0', 'M': [{'H': 'C3', 'M': 'authenticationExpiring', 'A': []}]}
                    LOG.debug("%s: private subscription authentication expired. %s", self.id, msg)
                else:
                    LOG.warning("%s: Invalid message type %s", self.id, msg)
        elif 'E' in msg:
            LOG.error("%s: Error from exchange %s", self.id, msg)

    async def generate_token(self, conn: AsyncConnection):
        timestamp = str(int(time.time()) * 1000)
        random_content = str(uuid.uuid4())
        content = timestamp + random_content
        signed_content = hmac.new(self.key_secret.encode(), content.encode(), hashlib.sha512).hexdigest()

        msg = {'A': [self.key_id, timestamp, random_content, signed_content], 'H': 'c3', 'I': 0, 'M': 'Authenticate'}
        # There is only subacounts on BITTREX for institutional customers.
        # if self.subaccount:
        #     msg['args']['subaccount'] = self.subaccount
        await conn.write(json.dumps(msg))

    async def authenticate(self, conn: AsyncConnection):
        if self.requires_authentication:
            await self.generate_token(conn)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        # H: Hub, M: Message, A: Args, I: Internal ID
        # For more signalR info see:
        # https://blog.3d-logic.com/2015/03/29/signalr-on-the-wire-an-informal-description-of-the-signalr-protocol/
        # http://blogs.microsoft.co.il/applisec/2014/03/12/signalr-message-format/
        for chan in self.subscription:
            channel = self.exchange_channel_to_std(chan)
            i = 1
            # If we subscribe to ORDER_INFO, then that is registered for all symbols in our account.
            # if channel in (ORDER_INFO, BALANCES):
            if self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                msg = {'A': ([chan],), 'H': 'c3', 'I': i, 'M': 'Subscribe'}
                await conn.write(json.dumps(msg))
                i += 1
            else:
                for symbol in self.subscription[chan]:
                    if channel == L2_BOOK:
                        msg = {'A': ([chan.format(symbol, self.__depth())],), 'H': 'c3', 'I': i, 'M': 'Subscribe'}
                    elif channel in (TRADES, TICKER):
                        msg = {'A': ([chan.format(symbol)],), 'H': 'c3', 'I': i, 'M': 'Subscribe'}
                        LOG.info(f"loop subscribed: {([chan.format(symbol)],)}")
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

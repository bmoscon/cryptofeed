'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from decimal import Decimal
from functools import partial
import logging
import time
from typing import Dict, List, Tuple, Callable
import requests
import hmac
import base64
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import CALL, CANCELLED, FILL_OR_KILL, FUTURES, IMMEDIATE_OR_CANCEL, MAKER_OR_CANCEL, MARKET, OKEX, LIQUIDATIONS, BUY, OPEN, OPTION, PARTIAL, PERPETUAL, PUT, SELL, FILLED, ASK, BID, FUNDING, L2_BOOK, OPEN_INTEREST, TICKER, TRADES, ORDER_INFO, SPOT, UNFILLED, LIMIT
from cryptofeed.feed import Feed
from cryptofeed.exceptions import BadChecksum
from cryptofeed.symbols import Symbol
from cryptofeed.types import OrderBook, Trade, Ticker, Funding, OpenInterest, Liquidation, OrderInfo


LOG = logging.getLogger("feedhandler")


class OKEx(Feed):
    id = OKEX
    api = 'https://www.okex.com/api/'
    symbol_endpoint = ['https://www.okex.com/api/v5/public/instruments?instType=SPOT', 'https://www.okex.com/api/v5/public/instruments?instType=SWAP', 'https://www.okex.com/api/v5/public/instruments?instType=FUTURES', 'https://www.okex.com/api/v5/public/instruments?instType=OPTION&uly=BTC-USD', 'https://www.okex.com/api/v5/public/instruments?instType=OPTION&uly=ETH-USD']
    websocket_channels = {
        L2_BOOK: 'books-l2-tbt',
        TRADES: 'trades',
        TICKER: 'tickers',
        FUNDING: 'funding-rate',
        OPEN_INTEREST: 'open-interest',
        LIQUIDATIONS: LIQUIDATIONS,
        ORDER_INFO: 'orders',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1000.0

    @classmethod
    def _parse_symbol_data(cls, data: list) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            for e in entry['data']:
                expiry = None
                otype = None
                stype = e['instType'].lower()
                strike = None

                if stype == SPOT:
                    base = e['baseCcy']
                    quote = e['quoteCcy']
                elif stype == FUTURES:
                    base, quote, expiry = e['instId'].split("-")
                elif stype == OPTION:
                    base, quote, expiry, strike, otype = e['instId'].split("-")
                    otype = PUT if otype == 'P' else CALL
                elif stype == 'swap':
                    # this is a perpetual swap (aka perpetual futures contract), not a real swap
                    stype = PERPETUAL
                    base, quote, _ = e['instId'].split("-")

                s = Symbol(base, quote, expiry_date=expiry, type=stype, option_type=otype, strike_price=strike)
                ret[s.normalized] = e['instId']
                info['tick_size'][s.normalized] = e['tickSz']
                info['instrument_type'][s.normalized] = stype

        return ret, info

    def __init__(self, **kwargs):
        self.addresses = {'public': 'wss://ws.okex.com:8443/ws/v5/public',
                          'private': 'wss://ws.okex.com:8443/ws/v5/private'}
        super().__init__(self.addresses, **kwargs)
        self.ws_defaults['compression'] = None
        self.instrument_type_map = {'perpetual': 'SWAP',
                                    'spot': 'MARGIN'}

    async def _liquidations(self, pairs: list):
        last_update = defaultdict(dict)
        """
        for PERP liquidations, the following arguments are required: uly, state
        for FUTURES liquidations, the following arguments are required: uly, state, alias
        FUTURES, MARGIN and OPTION liquidation request not currently supported by the below
        """

        while True:
            for pair in pairs:
                if 'PERP' in pair:
                    instrument_type = 'SWAP'
                    uly = pair.split("-")[0] + "-" + pair.split("-")[1]
                else:
                    continue

                for status in (FILLED, UNFILLED):
                    end_point = f"{self.api}v5/public/liquidation-orders?instType={instrument_type}&limit=100&state={status}&uly={uly}"
                    data = await self.http_conn.read(end_point)
                    data = json.loads(data, parse_float=Decimal)
                    timestamp = time.time()
                    if len(data['data'][0]['details']) == 0 or (len(data['data'][0]['details']) > 0 and last_update.get(pair) == data['data'][0]['details'][0]):
                        continue
                    for entry in data['data'][0]['details']:
                        if pair in last_update:
                            if entry == last_update[pair].get(status):
                                break

                        liq = Liquidation(
                            self.id,
                            pair,
                            BUY if entry['side'] == 'buy' else SELL,
                            None,
                            Decimal(entry['bkPx']),
                            status,
                            None,
                            raw=data
                        )
                        await self.callback(LIQUIDATIONS, liq, timestamp)
                    last_update[pair][status] = data['data'][0]['details'][0]
                await asyncio.sleep(0.1)
            await asyncio.sleep(60)

    def __reset(self):
        self._l2_book = {}

    @classmethod
    def instrument_type(cls, symbol: str):
        return cls.info()['instrument_type'][symbol]

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {"arg": {"channel": "tickers", "instId": "LTC-USD-200327"}, "data": [{"instType": "SWAP","instId": "LTC-USD-SWAP","last": "9999.99","lastSz": "0.1","askPx": "9999.99","askSz": "11","bidPx": "8888.88","bidSz": "5","open24h": "9000","high24h": "10000","low24h": "8888.88","volCcy24h": "2222","vol24h": "2222","sodUtc0": "2222","sodUtc8": "2222","ts": "1597026383085"}]}
        """
        pair = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
        for update in msg['data']:
            update_timestamp = self.timestamp_normalize(int(update['ts']))
            t = Ticker(
                self.id,
                pair,
                Decimal(update['bidPx']) if update['bidPx'] else Decimal(0),
                Decimal(update['askPx']) if update['askPx'] else Decimal(0),
                update_timestamp,
                raw=update
            )
            await self.callback(TICKER, t, timestamp)

    async def _open_interest(self, msg: dict, timestamp: float):
        """
        {
            'arg': {
                'channel': 'open-interest',
                'instId': 'BTC-USDT-SWAP
            },
            'data': [
                {
                    'instId': 'BTC-USDT-SWAP',
                    'instType': 'SWAP',
                    'oi':'565474',
                    'oiCcy': '5654.74',
                    'ts': '1630338003010'
                }
            ]
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
        for update in msg['data']:
            oi = OpenInterest(
                self.id,
                symbol,
                Decimal(update['oi']),
                self.timestamp_normalize(int(update['ts'])),
                raw=update
            )
            await self.callback(OPEN_INTEREST, oi, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            "arg": {
                "channel": "trades",
                "instId": "BTC-USD-191227"
            },
            "data": [
                {
                    "instId": "BTC-USD-191227",
                    "tradeId": "9",
                    "px": "0.016",
                    "sz": "50",
                    "side": "buy",
                    "ts": "1597026383085"
                }
            ]
        }
        """
        for trade in msg['data']:
            t = Trade(
                self.id,
                self.exchange_symbol_to_std_symbol(trade['instId']),
                BUY if trade['side'] == 'buy' else SELL,
                Decimal(trade['sz']),
                Decimal(trade['px']),
                self.timestamp_normalize(int(trade['ts'])),
                id=trade['tradeId'],
                raw=trade
            )
            await self.callback(TRADES, t, timestamp)

    async def _funding(self, msg: dict, timestamp: float):
        for update in msg['data']:
            f = Funding(
                self.id,
                self.exchange_symbol_to_std_symbol(update['instId']),
                None,
                Decimal(update['fundingRate']),
                None,
                self.timestamp_normalize(int(update['fundingTime'])),
                predicted_rate=Decimal(update['nextFundingRate']),
                raw=update
            )
            await self.callback(FUNDING, f, timestamp)

    async def _book(self, msg: dict, timestamp: float):
        if msg['action'] == 'snapshot':
            # snapshot
            pair = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
            for update in msg['data']:
                bids = {Decimal(price): Decimal(amount) for price, amount, *_ in update['bids']}
                asks = {Decimal(price): Decimal(amount) for price, amount, *_ in update['asks']}
                self._l2_book[pair] = OrderBook(self.id, pair, max_depth=self.max_depth, checksum_format='OKEX', bids=bids, asks=asks)

                if self.checksum_validation and self._l2_book[pair].book.checksum() != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(int(update['ts'])), checksum=update['checksum'] & 0xFFFFFFFF, raw=msg)
        else:
            # update
            pair = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
            for update in msg['data']:
                delta = {BID: [], ASK: []}

                for side in ('bids', 'asks'):
                    s = BID if side == 'bids' else ASK
                    for price, amount, *_ in update[side]:
                        price = Decimal(price)
                        amount = Decimal(amount)
                        if amount == 0:
                            if price in self._l2_book[pair].book[s]:
                                delta[s].append((price, 0))
                                del self._l2_book[pair].book[s][price]
                        else:
                            delta[s].append((price, amount))
                            self._l2_book[pair].book[s][price] = amount
                if self.checksum_validation and self._l2_book[pair].book.checksum() != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(L2_BOOK, self._l2_book[pair], timestamp, timestamp=self.timestamp_normalize(int(update['ts'])), raw=msg, delta=delta, checksum=update['checksum'] & 0xFFFFFFFF)

    async def _order(self, msg: dict, timestamp: float):
        '''
        {
          "arg": {
            "channel": "orders",
            "instType": "FUTURES",
            "instId": "BTC-USD-200329"
          },
          "data": [
            {
              "instType": "FUTURES",
              "instId": "BTC-USD-200329",
              "ccy": "BTC",
              "ordId": "312269865356374016",
              "clOrdId": "b1",
              "tag": "",
              "px": "999",
              "sz": "333",
              "notionalUsd": "",
              "ordType": "limit",
              "side": "buy",
              "posSide": "long",
              "tdMode": "cross",
              "tgtCcy": "",
              "fillSz": "0",
              "fillPx": "long",
              "tradeId": "0",
              "accFillSz": "323",
              "fillNotionalUsd": "",
              "fillTime": "0",
              "fillFee": "0.0001",
              "fillFeeCcy": "BTC",
              "execType": "T",
              "state": "canceled",
              "avgPx": "0",
              "lever": "20",
              "tpTriggerPx": "0",
              "tpOrdPx": "20",
              "slTriggerPx": "0",
              "slOrdPx": "20",
              "feeCcy": "",
              "fee": "",
              "rebateCcy": "",
              "rebate": "",
              "tgtCcy":"",
              "pnl": "",
              "category": "",
              "uTime": "1597026383085",
              "cTime": "1597026383085",
              "reqId": "",
              "amendResult": "",
              "code": "0",
              "msg": ""
            }
          ]
        }
        '''
        status = msg['data'][0]['state']
        if status == 'canceled':
            status == CANCELLED
        elif status == 'live':
            status == OPEN
        elif status == 'partially-filled':
            status = PARTIAL
        elif status == 'filled':
            status = FILLED

        o_type = msg['data'][0]['ordType']
        if o_type == 'market':
            o_type = MARKET
        elif o_type == 'post_only':
            o_type = MAKER_OR_CANCEL
        elif o_type == 'fok':
            o_type = FILL_OR_KILL
        elif o_type == 'ioc':
            o_type = IMMEDIATE_OR_CANCEL
        elif o_type == 'limit':
            o_type = LIMIT

        oi = OrderInfo(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['data'][0]['instId'].upper()),
            msg['data'][0]['ordId'],
            BUY if msg['data'][0]['side'].lower() == 'buy' else SELL,
            status,
            o_type,
            Decimal(msg['data'][0]['fillPx']) if msg['data'][0]['fillPx'] else Decimal(0),
            Decimal(msg['data'][0]['fillSz']) if msg['data'][0]['fillSz'] else Decimal(0),
            Decimal(msg['data'][0]['sz']) - Decimal(msg['data'][0]['accFillSz']) if msg['data'][0]['accFillSz'] else Decimal(0),
            self.timestamp_normalize(int(msg['data'][0]['uTime'])),
            raw=msg
        )
        await self.callback(ORDER_INFO, oi, timestamp)

    async def _login(self, msg: dict, timestamp: float):
        LOG.debug('%s: Websocket logged in? %s', self.id, msg['code'])

    async def message_handler(self, msg: str, conn, timestamp: float):
        # DEFLATE compression, no header
        # msg = zlib.decompress(msg, -15)
        # not required, as websocket now set to "Per-Message Deflate"
        msg = json.loads(msg, parse_float=Decimal)

        if 'event' in msg:
            if msg['event'] == 'error':
                LOG.error("%s: Error: %s", self.id, msg)
            elif msg['event'] == 'subscribe':
                pass
            elif msg['event'] == 'login':
                await self._login(msg, timestamp)
            else:
                LOG.warning("%s: Unhandled event %s", self.id, msg)
        elif 'arg' in msg:
            if 'books-l2-tbt' in msg['arg']['channel']:
                await self._book(msg, timestamp)
            elif 'tickers' in msg['arg']['channel']:
                await self._ticker(msg, timestamp)
            elif 'trades' in msg['arg']['channel']:
                await self._trade(msg, timestamp)
            elif 'funding-rate' in msg['arg']['channel']:
                await self._funding(msg, timestamp)
            elif 'orders' in msg['arg']['channel']:
                await self._order(msg, timestamp)
            elif 'open-interest' in msg['arg']['channel']:
                await self._open_interest(msg, timestamp)
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []
        if any(self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in self.subscription):
            ret.append((WSAsyncConn(self.address['private'], self.id, **self.ws_defaults),
                        partial(self.subscribe, private=True), self.message_handler, self.authenticate))
        if any(not self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in self.subscription):
            ret.append((WSAsyncConn(self.address['public'], self.id, **self.ws_defaults),
                        partial(self.subscribe, private=False), self.message_handler, self.__no_auth))
        return ret

    async def subscribe(self, connection: AsyncConnection, private: bool = False):
        pri_channels = []
        pub_channels = []
        if private:
            for chan in self.subscription:
                if self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                    for pair in self.subscription[chan]:
                        pri_channels.append(self.build_subscription(chan, pair))
        else:
            for chan in self.subscription:
                if not self.is_authenticated_channel(self.exchange_channel_to_std(chan)):
                    for pair in self.subscription[chan]:
                        pub_channels.append(self.build_subscription(chan, pair))

        if pri_channels:
            msg = {"op": "subscribe",
                   "args": pri_channels}
            LOG.debug(f'{connection.uuid}: Subscribing to private channels with message {msg}')
            await connection.write(json.dumps(msg))

        if pub_channels:
            msg = {"op": "subscribe",
                   "args": pub_channels}
            LOG.debug(f'{connection.uuid}: Subscribing to public channels with message {msg}')
            await connection.write(json.dumps(msg))

    async def authenticate(self, conn: AsyncConnection):
        if self.requires_authentication:
            auth = self._auth(self.key_id, self.key_secret)
            LOG.debug(f"{conn.uuid}: Authenticating with message: {auth}")
            await conn.write(json.dumps(auth))
            await asyncio.sleep(1)

    def _auth(self, key_id, key_secret) -> str:
        timestamp, sign = self._generate_token(key_id, key_secret)
        login_param = {"op": "login", "args": [{"apiKey": self.key_id, "passphrase": self.config.okex.key_passphrase, "timestamp": timestamp, "sign": sign.decode("utf-8")}]}
        return login_param

    async def __no_auth(self, conn: AsyncConnection):
        pass

    def build_subscription(self, channel: str, ticker: str) -> dict:
        if channel in ['positions', 'orders']:
            subscription_dict = {"channel": channel,
                                 "instType": self.inst_type_to_okex_type(ticker),
                                 "instId": ticker}
        else:
            subscription_dict = {"channel": channel,
                                 "instId": ticker}
        return subscription_dict

    def inst_type_to_okex_type(self, ticker):
        sym = self.exchange_symbol_to_std_symbol(ticker)
        instrument_type = self.instrument_type(sym)
        return self.instrument_type_map[instrument_type]

    def _get_server_time(self):
        endpoint = "v5/public/time"
        response = requests.get(self.api + endpoint)
        if response.status_code == 200:
            return response.json()['data'][0]['ts']
        else:
            return ""

    def _server_timestamp(self):
        server_time = self._get_server_time()
        return int(server_time) / 1000

    def _create_sign(self, timestamp: str, key_secret: str):
        message = timestamp + 'GET' + '/users/self/verify'
        mac = hmac.new(bytes(key_secret, encoding='utf8'), bytes(message, encoding='utf-8'), digestmod='sha256')
        d = mac.digest()
        sign = base64.b64encode(d)
        return sign

    def _generate_token(self, key_id: str, key_secret: str) -> dict:
        timestamp = str(self._server_timestamp())
        sign = self._create_sign(timestamp, key_secret)
        return timestamp, sign

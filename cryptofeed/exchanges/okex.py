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

from yapic import json

from cryptofeed.auth.okex import generate_token
from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import CALL, CANCELLED, CANCELLING, FAILED, FILL_OR_KILL, FUTURES, IMMEDIATE_OR_CANCEL, MAKER_OR_CANCEL, MARKET, OKEX, LIQUIDATIONS, BUY, OPEN, OPTION, PARTIAL, PERPETUAL, PUT, SELL, FILLED, ASK, BID, FUNDING, L2_BOOK, OPEN_INTEREST, SUBMITTING, TICKER, TRADES, ORDER_INFO, SPOT, UNFILLED
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
        ORDER_INFO: ORDER_INFO,
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

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        for chan in self.subscription:
            if not self.is_authenticated_channel(chan):
                if chan == LIQUIDATIONS:
                    continue
                for symbol in self.subscription[chan]:
                    sym = self.exchange_symbol_to_std_symbol(symbol)
                    instrument_type = self.instrument_type(sym)
                    if instrument_type != PERPETUAL and 'funding' in chan:
                        continue  # No funding for spot, futures and options
                    request = {"op": "subscribe", "args": [{"channel": chan, "instId": symbol}]}
                    await conn.write(json.dumps(request))

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
            "table":"spot/order",
            "data":[
                {
                    "client_oid":"",
                    "filled_notional":"0",
                    "filled_size":"0",
                    "instrument_id":"ETC-USDT",
                    "last_fill_px":"0",
                    "last_fill_qty":"0",
                    "last_fill_time":"1970-01-01T00:00:00.000Z",
                    "margin_trading":"1",
                    "notional":"",
                    "order_id":"3576398568830976",
                    "order_type":"0",
                    "price":"5.826",
                    "side":"buy",
                    "size":"0.1",
                    "state":"0",
                    "status":"open",
                    "timestamp":"2019-09-24T06:45:11.394Z",
                    "type":"limit",
                    "created_at":"2019-09-24T06:45:11.394Z"
                }
            ]
        }
        '''
        status = msg['data'][0]['state']
        if status == -1:
            status = FAILED
        elif status == -1:
            status == CANCELLED
        elif status == 0:
            status == OPEN
        elif status == 1:
            status = PARTIAL
        elif status == 2:
            status = FILLED
        elif status == 3:
            status = SUBMITTING
        elif status == 4:
            status = CANCELLING

        o_type = msg['data'][0]['ordType']
        if o_type == 0:
            o_type = MARKET
        elif o_type == 1:
            o_type = MAKER_OR_CANCEL
        elif o_type == 2:
            o_type = FILL_OR_KILL
        elif o_type == 3:
            o_type = IMMEDIATE_OR_CANCEL

        oi = OrderInfo(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['data'][0]['instId'].upper()),
            msg['data'][0]['ordId'],
            BUY if msg['data'][0]['side'].lower() == 'buy' else SELL,
            status,
            o_type,
            Decimal(msg['data'][0]['filled_notional'] / msg['data'][0]['filled_size']),
            Decimal(msg['data'][0]['filled_size']),
            msg['data'][0]['uTime'].timestamp(),
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
        for channel in self.subscription:
            if self.is_authenticated_channel(channel):
                for s in self.subscription[channel]:
                    ret.append((WSAsyncConn(self.addresses['private'], self.id, **self.ws_defaults), partial(self.user_order_subscribe, symbol=s), self.message_handler, self.authenticate))
        ret.append((WSAsyncConn(self.addresses['public'], self.id, **self.ws_defaults), self.subscribe, self.message_handler, self.authenticate))
        return ret

    async def user_order_subscribe(self, conn: AsyncConnection, symbol=None):
        self.__reset()
        timestamp, sign = generate_token(self.key_id, self.key_secret)
        login_param = {"op": "login", "args": [{"apiKey": self.key_id, "passphrase": self.config.okex.key_passphrase, "timestamp": timestamp, "sign": sign.decode("utf-8")}]}
        login_str = json.dumps(login_param)
        await conn.write(login_str)
        await asyncio.sleep(5)
        instrument_type = self.instrument_type(symbol)
        sub_param = {"op": "subscribe", "args": [{"channel": "orders", "instType": instrument_type.upper(), "instId": symbol}]}
        sub_str = json.dumps(sub_param)
        await conn.write(sub_str)

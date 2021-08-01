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
import zlib
import time
from itertools import islice
from typing import Dict, List, Tuple, Callable

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.auth.okex import generate_token
from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import CALL, FUTURES, OKEX, LIQUIDATIONS, BUY, OPTION, PERPETUAL, PUT, SELL, FILLED, ASK, BID, FUNDING, L2_BOOK, OPEN_INTEREST, TICKER, TRADES, ORDER_INFO, SPOT
from cryptofeed.feed import Feed
from cryptofeed.util import split
from cryptofeed.exceptions import BadChecksum
from cryptofeed.symbols import Symbol


LOG = logging.getLogger("feedhandler")


class OKEx(Feed):
    """
    OKEx has the same api as OKCoin, just a different websocket endpoint
    """
    id = OKEX
    api = 'https://www.okex.com/api/'
    symbol_endpoint = ['https://www.okex.com/api/v5/public/instruments?instType=SPOT', 'https://www.okex.com/api/v5/public/instruments?instType=SWAP', 'https://www.okex.com/api/v5/public/instruments?instType=FUTURES', 'https://www.okex.com/api/v5/public/instruments?instType=OPTION&uly=BTC-USD', 'https://www.okex.com/api/v5/public/instruments?instType=OPTION&uly=ETH-USD']
    websocket_channels = {
        L2_BOOK: 'books-l2-tbt',
        TRADES: 'trades',
        TICKER: 'tickers',
        FUNDING: 'funding-rate',
        OPEN_INTEREST: 'tickers',
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

    async def _liquidations(self, pairs: list):
        last_update = {}
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
                    break

                for status in (0, 1):
                    end_point = f"{self.api}v5/public/liquidation-orders?instType={instrument_type}&limit=100&state={FILLED}&uly={uly}"
                    data = await self.http_conn.read(end_point)
                    data = json.loads(data, parse_float=Decimal)
                    timestamp = time.time()
                    if len(data['data'][0]['details']) == 0 or (len(data['data'][0]['details']) > 0 and last_update.get(pair) == data['data'][0]['details'][0]):
                        continue
                    for entry in data['data'][0]['details']:
                        if entry == last_update.get(pair):
                            break
                        await self.callback(LIQUIDATIONS,
                                            feed=self.id,
                                            symbol=pair,
                                            side=BUY if entry['side'] == 'buy' else SELL,
                                            leaves_quantity=None,
                                            price=Decimal(entry['bkPx']),
                                            order_id=None,
                                            status=FILLED,
                                            timestamp=timestamp,
                                            receipt_timestamp=timestamp
                                            )
                    last_update[pair] = data['data'][0]['details'][0]
                await asyncio.sleep(0.1)
            await asyncio.sleep(60)

    async def subscribe(self, conn: AsyncConnection):
        self.__reset()
        symbol_channels = list(self.get_channel_symbol_combinations())
        LOG.info("%s: Got %r combinations of pairs and channels", self.id, len(symbol_channels))

        if len(symbol_channels) == 0:
            LOG.info("%s: No websocket subscription", self.id)
            return False

        # Avoid error "Max frame length of 65536 has been exceeded" by limiting requests to some args
        for chunk in split.list_by_max_items(symbol_channels, 33):
            LOG.info("%s: Subscribe to %s args from %r to %r", self.id, len(chunk), chunk[0], chunk[-1])
            request = {"op": "subscribe", "args": chunk}
            await conn.write(json.dumps(request))

    def __reset(self):
        self._l2_book = {}
        self.open_interest = {}

    def __calc_checksum(self, pair):
        bid_it = reversed(self._l2_book[pair][BID])
        ask_it = iter(self._l2_book[pair][ASK])

        bids = (f"{bid}:{self._l2_book[pair][BID][bid]}" for bid in bid_it)
        bids = list(islice(bids, 25))
        asks = (f"{ask}:{self._l2_book[pair][ASK][ask]}" for ask in ask_it)
        asks = list(islice(asks, 25))

        if len(bids) == len(asks):
            combined = [val for pair in zip(bids, asks) for val in pair]
        elif len(bids) > len(asks):
            combined = [val for pair in zip(bids[:len(asks)], asks) for val in pair]
            combined += bids[len(asks):]
        else:
            combined = [val for pair in zip(bids, asks[:len(bids)]) for val in pair]
            combined += asks[len(bids):]
        computed = ":".join(combined).encode()
        return zlib.crc32(computed)

    @classmethod
    def instrument_type(cls, symbol: str):
        return cls.info()['instrument_type'][symbol]

    def get_channel_symbol_combinations(self):
        """
        "args": [{"channel": "tickers","instId": "LTC-USD-200327"},{"channel": "candle1m","instId": "LTC-USD-200327"}]
        """
        combos = []
        for chan in self.subscription:
            if not self.is_authenticated_channel(chan):
                if chan == LIQUIDATIONS:
                    continue
                for symbol in self.subscription[chan]:
                    d = {}
                    sym = self.exchange_symbol_to_std_symbol(symbol)
                    instrument_type = self.instrument_type(sym)
                    if instrument_type != PERPETUAL and 'funding' in chan:
                        continue  # No funding for spot, futures and options
                    d.update({"channel": chan, "instId": symbol})
                    combos.append(d)
        return combos

    async def _ticker(self, msg: dict, timestamp: float):
        """
        {"arg": {"channel": "tickers", "instId": "LTC-USD-200327"}, "data": [{"instType": "SWAP","instId": "LTC-USD-SWAP","last": "9999.99","lastSz": "0.1","askPx": "9999.99","askSz": "11","bidPx": "8888.88","bidSz": "5","open24h": "9000","high24h": "10000","low24h": "8888.88","volCcy24h": "2222","vol24h": "2222","sodUtc0": "2222","sodUtc8": "2222","ts": "1597026383085"}]}
        """
        for update in msg['data']:
            pair = msg['arg']['instId']
            update_timestamp = self.timestamp_normalize(int(update['ts']))
            await self.callback(TICKER,
                                feed=self.id,
                                symbol=pair,
                                bid=Decimal(update['bidPx']) if update['bidPx'] else Decimal(0),
                                ask=Decimal(update['askPx']) if update['askPx'] else Decimal(0),
                                timestamp=update_timestamp,
                                receipt_timestamp=timestamp)
            if 'open_interest' in update:
                oi = update['open_interest']
                if pair in self.open_interest and oi == self.open_interest[pair]:
                    continue
                self.open_interest[pair] = oi
                await self.callback(OPEN_INTEREST, feed=self.id, symbol=pair, open_interest=oi, timestamp=update_timestamp, receipt_timestamp=timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {"arg": {"channel": "trades","instId": "BTC-USD-191227"},"data": [{"instId": "BTC-USD-191227","tradeId": "9","px": "0.016","sz": "50","side": "buy","ts": "1597026383085"}]}
        """
        for trade in msg['data']:
            await self.callback(TRADES,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(trade['instId']),
                                order_id=trade['tradeId'],
                                side=BUY if trade['side'] == 'buy' else SELL,
                                amount=Decimal(trade['sz']),
                                price=Decimal(trade['px']),
                                timestamp=self.timestamp_normalize(int(trade['ts'])),
                                receipt_timestamp=timestamp
                                )

    async def _funding(self, msg: dict, timestamp: float):
        for update in msg['data']:
            await self.callback(FUNDING,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(update['instId']),
                                timestamp=self.timestamp_normalize(int(update['fundingTime'])),
                                receipt_timestamp=timestamp,
                                rate=update['fundingRate'],
                                estimated_rate=update['nextFundingRate'],
                                settlement_time=self.timestamp_normalize(int(update['fundingTime'])))

    async def _book(self, msg: dict, timestamp: float):
        if msg['action'] == 'snapshot':
            # snapshot
            pair = self.exchange_symbol_to_std_symbol(msg['arg']['instId'])
            for update in msg['data']:
                self._l2_book[pair] = {
                    BID: sd({
                        Decimal(price): Decimal(amount) for price, amount, *_ in update['bids']
                    }),
                    ASK: sd({
                        Decimal(price): Decimal(amount) for price, amount, *_ in update['asks']
                    })
                }

                if self.checksum_validation and self.__calc_checksum(pair) != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(self._l2_book[pair], L2_BOOK, pair, True, None, self.timestamp_normalize(int(update['ts'])), timestamp)
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
                            if price in self._l2_book[pair][s]:
                                delta[s].append((price, 0))
                                del self._l2_book[pair][s][price]
                        else:
                            delta[s].append((price, amount))
                            self._l2_book[pair][s][price] = amount
                if self.checksum_validation and self.__calc_checksum(pair) != (update['checksum'] & 0xFFFFFFFF):
                    raise BadChecksum
                await self.book_callback(self._l2_book[pair], L2_BOOK, pair, False, delta, self.timestamp_normalize(int(update['ts'])), timestamp)

    async def _order(self, msg: dict, timestamp: float):

        status = msg['data'][0]['state']
        keys = ('fillSz', 'sz')
        data = {k: Decimal(msg['data'][0][k]) for k in keys if k in msg['data'][0]}
        data.update({'clOrdId': msg['data'][0]['clOrdId']})
        data.update({'fillPx': msg['data'][0]['fillPx']})

        await self.callback(ORDER_INFO,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['data'][0]['instId'].upper()),  # This uses the REST endpoint format (lower case)
                            status=status,
                            order_id=msg['data'][0]['ordId'],
                            side=BUY if msg['data'][0]['side'].lower() == 'buy' else SELL,
                            order_type=msg['data'][0]['ordType'],
                            timestamp=msg['data'][0]['uTime'],
                            receipt_timestamp=timestamp,
                            **data
                            )

    async def _swap_order(self, msg: dict, timestamp: float):

        keys = ('filled_qty', 'last_fill_qty', 'price_avg', 'fee')
        data = {k: Decimal(msg['data'][0][k]) for k in keys if k in msg['data'][0]}

        await self.callback(ORDER_INFO,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['data'][0]['instrument_id'].upper()),  # This uses the REST endpoint format (lower case)
                            status=int(msg['data'][0]['state']),
                            order_id=msg['data'][0]['order_id'],
                            side=int(msg['data'][0]['type']),
                            order_type=int(msg['data'][0]['order_type']),
                            timestamp=msg['data'][0]['timestamp'].timestamp(),
                            receipt_timestamp=timestamp,
                            **data
                            )

    async def _login(self, msg: dict, timestamp: float):
        LOG.info('%s: Websocket logged in? %s', self.id, msg['code'])

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
        else:
            LOG.warning("%s: Unhandled message %s", self.id, msg)

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []
        for channel in self.subscription:
            if self.is_authenticated_channel(channel):
                for s in self.subscription[channel]:
                    ret.append((WSAsyncConn(self.addresses['private'], self.id, **self.ws_defaults), partial(self.user_order_subscribe, symbol=s), self.message_handler, self.authenticate))
            else:
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

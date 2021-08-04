'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from cryptofeed.symbols import Symbol
from functools import partial
import logging
from decimal import Decimal
from typing import Callable, Dict, List, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BUY, CANDLES, PHEMEX, L2_BOOK, SELL, TRADES, USER_DATA, LAST_PRICE
from cryptofeed.feed import Feed

import hmac
import time


LOG = logging.getLogger('feedhandler')


class Phemex(Feed):
    id = PHEMEX
    symbol_endpoint = 'https://api.phemex.com/exchange/public/cfg/v2/products'
    price_scale = {}
    valid_candle_intervals = ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1M', '1Q', '1Y')
    websocket_channels = {
        LAST_PRICE: 'tick.subscribe',
        USER_DATA: 'aop.subscribe',
        L2_BOOK: 'orderbook.subscribe',
        TRADES: 'trade.subscribe',
        CANDLES: 'kline.subscribe',
    }

    @classmethod
    def timestamp_normalize(cls, ts: float) -> float:
        return ts / 1_000_000_000.0

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']['products']:
            if entry['status'] != 'Listed':
                continue
            stype = entry['type'].lower()
            base, quote = entry['displaySymbol'].split(" / ")
            s = Symbol(base, quote, type=stype)
            ret[s.normalized] = entry['symbol']
            info['tick_size'][s.normalized] = entry['tickSize'] if 'tickSize' in entry else entry['quoteTickSize']
            info['instrument_type'][s.normalized] = stype
            # the price scale for spot symbols is not reported via the API but it is documented
            # here in the API docs: https://github.com/phemex/phemex-api-docs/blob/master/Public-Spot-API-en.md#spot-currency-and-symbols
            # the default value for spot is 10^8
            cls.price_scale[s.normalized] = 10 ** entry.get('priceScale', 8)
        return ret, info

    def __init__(self, candle_interval='1m', **kwargs):
        super().__init__('wss://phemex.com/ws', **kwargs)
        if candle_interval not in self.valid_candle_intervals:
            raise ValueError(f"Candle interval must be one of {self.valid_candle_intervals}")
        self.candle_interval = candle_interval
        seconds = [60, 300, 900, 1800, 3600, 14400, 86400, 604800, 2592000, 7776000, 31104000]
        self.candle_interval_map = {
            interval: second for interval, second in zip(self.valid_candle_intervals, seconds)
        }

        # Phemex only allows 5 connections, with 20 subscriptions per connection, check we arent over the limit
        items = len(self.subscription.keys()) * sum(len(v) for v in self.subscription.values())
        if items > 100:
            raise ValueError(f"{self.id} only allows a maximum of 100 symbol/channel subscriptions")

        self.__reset()

    def __reset(self):
        self._l2_book = {}

    async def _book(self, msg: dict, timestamp: float):
        """
        {
            'book': {
                'asks': [],
                'bids': [
                    [345475000, 14340]
                ]
            },
            'depth': 30,
            'sequence': 9047872983,
            'symbol': 'BTCUSD',
            'timestamp': 1625329629283990943,
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        ts = self.timestamp_normalize(msg['timestamp'])
        forced = False
        delta = {BID: [], ASK: []}

        if msg['type'] == 'snapshot':
            forced = True
            self._l2_book[symbol] = {
                BID: sd({Decimal(entry[0] / self.price_scale[symbol]): Decimal(entry[1]) for entry in msg['book']['bids']}),
                ASK: sd({Decimal(entry[0] / self.price_scale[symbol]): Decimal(entry[1]) for entry in msg['book']['asks']})
            }
        else:
            for key, side in (('asks', ASK), ('bids', BID)):
                for price, amount in msg['book'][key]:
                    price = Decimal(price / self.price_scale[symbol])
                    amount = Decimal(amount)
                    delta[side].append((price, amount))
                    if amount == 0:
                        # for some unknown reason deletes can be repeated in book updates
                        if price in self._l2_book[symbol][side]:
                            del self._l2_book[symbol][side][price]
                    else:
                        self._l2_book[symbol][side][price] = amount

        await self.book_callback(self._l2_book[symbol], L2_BOOK, symbol, forced, delta, ts, timestamp)

    async def _trade(self, msg: dict, timestamp: float):
        """
        {
            'sequence': 9047166781,
            'symbol': 'BTCUSD',
            'trades': [
                [1625326381255067545, 'Buy', 345890000, 323]
            ],
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])
        for ts, side, price, amount in msg['trades']:
            await self.callback(TRADES,
                                feed=self.id,
                                order_id=None,
                                symbol=symbol,
                                side=BUY if side == 'Buy' else SELL,
                                amount=Decimal(amount),
                                price=Decimal(price / self.price_scale[symbol]),
                                timestamp=self.timestamp_normalize(ts),
                                receipt_timestamp=timestamp)

    async def _candle(self, msg: dict, timestamp: float):
        """
        {
            'kline': [
                [1625332980, 60, 346285000, 346300000, 346390000, 346300000, 346390000, 49917, 144121225]
            ],
            'sequence': 9048385626,
            'symbol': 'BTCUSD',
            'type': 'incremental'
        }
        """
        symbol = self.exchange_symbol_to_std_symbol(msg['symbol'])

        for entry in msg['kline']:
            ts, _, _, open, high, low, close, _, volume = entry

            await self.callback(CANDLES,
                                feed=self.id,
                                symbol=symbol,
                                timestamp=timestamp,
                                receipt_timestamp=timestamp,
                                start=ts,
                                stop=ts + self.candle_interval_map[self.candle_interval],
                                interval=self.candle_interval,
                                trades=None,
                                open_price=Decimal(open / self.price_scale[symbol]),
                                close_price=Decimal(close / self.price_scale[symbol]),
                                high_price=Decimal(high / self.price_scale[symbol]),
                                low_price=Decimal(low / self.price_scale[symbol]),
                                volume=Decimal(volume),
                                closed=None)

    async def _last_price(self, msg: dict, timestamp: float):
        for s in self.normalized_symbols:
            if msg['symbol'][1:] in s:
                symbol = s
                break
        await self.callback(LAST_PRICE, feed=self.id,
                            symbol=symbol,
                            last_price=msg["last"] / 10 ** msg["scale"],
                            receipt_timestamp=timestamp)

    async def _user_data(self, msg: dict, timestamp: float):
        await self.callback(USER_DATA, feed=self.id, data=msg, receipt_timestamp=timestamp)

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        # Phemex only allows 5 connections, with 20 subscriptions per connection, so split the subscription into separate
        # connections if necessary
        ret = []
        sub_pair = []

        if self.std_channel_to_exchange(USER_DATA) in self.subscription:
            sub_pair.append([self.std_channel_to_exchange(USER_DATA), USER_DATA])

        for chan, symbols in self.subscription.items():
            if self.exchange_channel_to_std(chan) == USER_DATA:
                continue
            for sym in symbols:
                sub_pair.append([chan, sym])
                if len(sub_pair) == 20:
                    func = partial(self.subscribe, subs=sub_pair)
                    ret.append((WSAsyncConn(self.address, self.id, **self.ws_defaults), func, self.message_handler, self.authenticate))
                    sub_pair = []

        if len(sub_pair) > 0:
            func = partial(self.subscribe, subs=sub_pair)
            ret.append((WSAsyncConn(self.address, self.id, **self.ws_defaults), func, self.message_handler, self.authenticate))

        return ret

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):

        msg = json.loads(msg, parse_float=Decimal)

        if 'id' in msg and msg['id'] == 100:
            if not msg['error']:
                LOG.info("%s: Auth request result: %s", conn.uuid, msg['result']['status'])
                msg = json.dumps({"id": 101, "method": self.std_channel_to_exchange(USER_DATA), "params": []})
                LOG.debug(f"{conn.uuid}: Subscribing to authenticated channels: {msg}")
                await conn.write(msg)
            else:
                LOG.warning("%s: Auth unsuccessful: %s", conn.uuid, msg)
        elif 'id' in msg and msg['id'] == 101:
            if not msg['error']:
                LOG.info("%s: Subscribe to auth channels request result: %s", conn.uuid, msg['result']['status'])
            else:
                LOG.warning(f"{conn.uuid}: Subscription unsuccessful: {msg}")
        elif 'id' in msg and msg['id'] == 1 and not msg['error']:
            pass
        elif {'accounts', 'orders', 'positions'} <= set(msg) or 'position_info' in msg:
            await self._user_data(msg, timestamp)
        elif 'tick' in msg:
            await self._last_price(msg["tick"], timestamp)
        elif 'book' in msg:
            await self._book(msg, timestamp)
        elif 'trades' in msg:
            await self._trade(msg, timestamp)
        elif 'kline' in msg:
            await self._candle(msg, timestamp)
        elif 'result' in msg:
            if 'error' in msg and msg['error'] is not None:
                LOG.warning("%s: Error from exchange %s", conn.uuid, msg)
                return
            else:
                LOG.warning("%s: Unhandled 'result' message: %s", conn.uuid, msg)
        else:
            LOG.warning("%s: Invalid message type %s", conn.uuid, msg)

    async def subscribe(self, conn: AsyncConnection, subs=None):
        self.__reset()

        for chan, symbol in subs:
            if not self.exchange_channel_to_std(chan) == USER_DATA:
                msg = {"id": 1, "method": chan, "params": [symbol]}
                if self.exchange_channel_to_std(chan) == CANDLES:
                    msg['params'] = [symbol, self.candle_interval_map[self.candle_interval]]
                elif self.exchange_channel_to_std(chan) == LAST_PRICE:
                    base = self.exchange_symbol_to_std_symbol(symbol).split('-')[0]
                    msg['params'] = [f'.{base}']
                LOG.debug(f"{conn.uuid}: Sending subscribe request to public channel: {msg}")
                await conn.write(json.dumps(msg))

    async def authenticate(self, conn: AsyncConnection):
        if any(self.is_authenticated_channel(self.exchange_channel_to_std(chan)) for chan in self.subscription):
            auth = json.dumps(self._auth(self.key_id, self.key_secret))
            LOG.debug(f"{conn.uuid}: Sending authentication request with message {auth}")
            await conn.write(auth)

    def _auth(self, key_id, key_secret, session_id=100):
        # https://github.com/phemex/phemex-api-docs/blob/master/Public-Contract-API-en.md#api-user-authentication
        expires = int((time.time() + 60))
        signature = str(hmac.new(bytes(key_secret, 'utf-8'), bytes(f'{key_id}{expires}', 'utf-8'), digestmod='sha256').hexdigest())
        auth = {"method": "user.auth", "params": ["API", key_id, signature, expires], "id": session_id}
        return auth

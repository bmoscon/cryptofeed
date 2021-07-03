'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
from functools import partial
import logging
from decimal import Decimal
from typing import Callable, Dict, List, Tuple

from sortedcontainers import SortedDict as sd
from yapic import json

from cryptofeed.connection import AsyncConnection, WSAsyncConn
from cryptofeed.defines import BID, ASK, BUY, CANDLES, PHEMEX, L2_BOOK, SELL, TRADES
from cryptofeed.feed import Feed
from cryptofeed.standards import normalize_channel, timestamp_normalize


LOG = logging.getLogger('feedhandler')


class Phemex(Feed):
    id = PHEMEX
    symbol_endpoint = 'https://api.phemex.com/exchange/public/cfg/v2/products'
    price_scale = {}
    valid_candle_intervals = ('1m', '5m', '15m', '30m', '1h', '4h', '1d', '1M', '1Q', '1Y')

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data['data']['products']:
            if entry['status'] != 'Listed':
                continue
            normalized = entry['displaySymbol'].replace(" / ", symbol_separator)
            ret[normalized] = entry['symbol']
            info['tick_size'][normalized] = entry['tickSize'] if 'tickSize' in entry else entry['quoteTickSize']
            info['instrument_type'][normalized] = entry['type'].lower()
            # the price scale for spot symbols is not reported via the API but it is documented
            # here in the API docs: https://github.com/phemex/phemex-api-docs/blob/master/Public-Spot-API-en.md#spot-currency-and-symbols
            # the default value for spot is 10^8
            cls.price_scale[normalized] = 10 ** entry.get('priceScale', 8)
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
        self.l2_book = {}

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
        ts = timestamp_normalize(self.id, msg['timestamp'])
        forced = False
        delta = {BID: [], ASK: []}

        if msg['type'] == 'snapshot':
            forced = True
            self.l2_book[symbol] = {
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
                        if price in self.l2_book[symbol][side]:
                            del self.l2_book[symbol][side][price]
                    else:
                        self.l2_book[symbol][side][price] = amount

        await self.book_callback(self.l2_book[symbol], L2_BOOK, symbol, forced, delta, ts, timestamp)

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
                                timestamp=timestamp_normalize(self.id, ts),
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

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        # Phemex only allows 5 connections, with 20 subscriptions per connection, so split the subscription into separate
        # connections if necessary
        ret = []
        sub_pair = []

        for chan, symbols in self.subscription.items():
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

        if 'book' in msg:
            await self._book(msg, timestamp)
        elif 'trades' in msg:
            await self._trade(msg, timestamp)
        elif 'kline' in msg:
            await self._candle(msg, timestamp)
        elif 'result' in msg:
            if 'error' in msg and msg['error'] is not None:
                LOG.warning("%s: Error from exchange %s", self.id, msg)
            return
        else:
            LOG.warning("%s: Invalid message type %s", self.id, msg)

    async def subscribe(self, conn: AsyncConnection, subs=None):
        self.__reset()

        for chan, symbol in subs:
            msg = {"id": 1, "method": chan, "params": [symbol]}
            if normalize_channel(self.id, chan) == CANDLES:
                msg['params'] = [symbol, self.candle_interval_map[self.candle_interval]]
            await conn.write(json.dumps(msg))

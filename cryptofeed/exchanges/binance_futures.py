'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from asyncio import create_task
from decimal import Decimal
import logging
import time
from typing import List, Tuple, Callable, Dict

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll, HTTPConcurrentPoll
from cryptofeed.defines import BINANCE_FUTURES, FUNDING, LIQUIDATIONS, OPEN_INTEREST, PERPETUAL, FUTURE, PREMIUM_INDEX
from cryptofeed.exchanges.binance import Binance
from cryptofeed.exchanges.mixins.binance_rest import BinanceFuturesRestMixin
from cryptofeed.standards import timestamp_normalize

LOG = logging.getLogger('feedhandler')


class BinanceFuturesInstrument():
    def __init__(self, instrument_name):
        self.instrument_name = instrument_name
        instrument_properties = instrument_name.split('_')
        self.pair = instrument_properties[0]
        pair_arr = instrument_properties[0].split('-')
        self.base = pair_arr[0]
        self.quote = pair_arr[1]

        if len(pair_arr) == 3 and pair_arr[2].lower() == PREMIUM_INDEX:
            self.instrument_type = PREMIUM_INDEX
        elif len(instrument_properties) == 1:
            self.instrument_type = PERPETUAL
        else:
            self.instrument_type = FUTURE
            self.expiry_date_str = instrument_properties[1]


class BinanceFutures(Binance, BinanceFuturesRestMixin):
    id = BINANCE_FUTURES
    symbol_endpoint = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
    valid_depths = [5, 10, 20, 50, 100, 500, 1000]
    valid_depth_intervals = {'100ms', '250ms', '500ms'}

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        base, info = super()._parse_symbol_data(data)
        add = {}
        for symbol, orig in base.items():
            if "_" in orig:
                continue
            add[f"{symbol.replace('PERP', 'PINDEX')}"] = f"p{orig}"
        base.update(add)
        return base, info

    def __init__(self, **kwargs):
        self.websocket_channels.update({
            FUNDING: 'markPrice',
            OPEN_INTEREST: 'open_interest',
            LIQUIDATIONS: 'forceOrder'
        })
        super().__init__(**kwargs)
        # overwrite values previously set by the super class Binance
        self.ws_endpoint = 'wss://fstream.binance.com'
        self.rest_endpoint = 'https://fapi.binance.com/fapi/v1'
        self.address = self._address()

    @staticmethod
    def get_instrument_objects():
        instruments = BinanceFutures.get_instruments()
        return [BinanceFuturesInstrument(instrument) for instrument in instruments]

    @staticmethod
    def convert_to_instrument_object(instrument_name):
        return BinanceFuturesInstrument(instrument_name)

    def _check_update_id(self, pair: str, msg: dict) -> Tuple[bool, bool, bool]:
        skip_update = False
        forced = not self.forced[pair]
        current_match = self.last_update_id[pair] == msg['u']

        if forced and msg['u'] < self.last_update_id[pair]:
            skip_update = True
        elif forced and msg['U'] <= self.last_update_id[pair] <= msg['u']:
            self.last_update_id[pair] = msg['u']
            self.forced[pair] = True
        elif not forced and self.last_update_id[pair] == msg['pu']:
            self.last_update_id[pair] = msg['u']
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            skip_update = True
        return skip_update, forced, current_match

    async def _open_interest(self, msg: dict, timestamp: float):
        """
        {
            "openInterest": "10659.509",
            "symbol": "BTCUSDT",
            "time": 1589437530011   // Transaction time
        }
        """
        pair = msg['symbol']
        oi = msg['openInterest']
        if oi != self.open_interest.get(pair, None):
            await self.callback(OPEN_INTEREST,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(pair),
                                open_interest=oi,
                                timestamp=self.self.timestamp_normalize(msg['time']),
                                receipt_timestamp=time.time()
                                )
            self.open_interest[pair] = oi

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []
        if self.address:
            ret = super().connect()
        PollCls = HTTPConcurrentPoll if self.concurrent_http else HTTPPoll
        for chan in set(self.subscription):
            if chan == 'open_interest':
                addrs = [f"{self.rest_endpoint}/openInterest?symbol={pair}" for pair in self.subscription[chan]]
                ret.append((PollCls(addrs, self.id, delay=60.0, sleep=1.0, proxy=self.http_proxy), self.subscribe, self.message_handler, self.authenticate))
        return ret

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Handle REST endpoint messages first
        if 'openInterest' in msg:
            coro = self._open_interest(msg, timestamp)
            if self.concurrent_http:
                return create_task(coro)
            return await coro

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        pair, _ = msg['stream'].split('@', 1)
        msg = msg['data']

        pair = pair.upper()

        msg_type = msg.get('e')
        if msg_type == 'bookTicker':
            await self._ticker(msg, timestamp)
        elif msg_type == 'depthUpdate':
            await self._book(msg, pair, timestamp)
        elif msg_type == 'aggTrade':
            await self._trade(msg, timestamp)
        elif msg_type == 'forceOrder':
            await self._liquidations(msg, timestamp)
        elif msg_type == 'markPriceUpdate':
            await self._funding(msg, timestamp)
        elif msg_type == '24hrMiniTicker':
            await self._volume(msg, timestamp)
        elif msg['e'] == 'kline':
            await self._candle(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

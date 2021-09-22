'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from asyncio import create_task
from decimal import Decimal
import logging
from typing import List, Tuple, Callable, Dict

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll, HTTPConcurrentPoll
from cryptofeed.defines import BALANCES, BINANCE_FUTURES, FUNDING, LIQUIDATIONS, OPEN_INTEREST, POSITIONS
from cryptofeed.exchanges.binance import Binance
from cryptofeed.exchanges.mixins.binance_rest import BinanceFuturesRestMixin
from cryptofeed.types import OpenInterest

LOG = logging.getLogger('feedhandler')


class BinanceFutures(Binance, BinanceFuturesRestMixin):
    id = BINANCE_FUTURES
    symbol_endpoint = 'https://fapi.binance.com/fapi/v1/exchangeInfo'
    listen_key_endpoint = 'listenKey'
    valid_depths = [5, 10, 20, 50, 100, 500, 1000]
    valid_depth_intervals = {'100ms', '250ms', '500ms'}
    websocket_channels = {
        **Binance.websocket_channels,
        FUNDING: 'markPrice',
        OPEN_INTEREST: 'open_interest',
        LIQUIDATIONS: 'forceOrder',
        POSITIONS: POSITIONS
    }

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

    def __init__(self, open_interest_interval=1.0, **kwargs):
        """
        open_interest_interval: flaot
            time in seconds between open_interest polls
        """
        super().__init__(**kwargs)
        # overwrite values previously set by the super class Binance
        self.ws_endpoint = 'wss://fstream.binance.com'
        self.rest_endpoint = 'https://fapi.binance.com/fapi/v1'
        self.address = self._address()
        self.ws_defaults['compression'] = None

        self.open_interest_interval = open_interest_interval

    def _check_update_id(self, pair: str, msg: dict) -> bool:
        if self._l2_book[pair].delta is None and msg['u'] < self.last_update_id[pair]:
            return True
        elif msg['U'] <= self.last_update_id[pair] <= msg['u']:
            self.last_update_id[pair] = msg['u']
            return False
        elif self.last_update_id[pair] == msg['pu']:
            self.last_update_id[pair] = msg['u']
            return False
        else:
            self._reset()
            LOG.warning("%s: Missing book update detected, resetting book", self.id)
            return True

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
        if oi != self._open_interest_cache.get(pair, None):
            o = OpenInterest(
                self.id,
                self.exchange_symbol_to_std_symbol(pair),
                Decimal(oi),
                self.timestamp_normalize(msg['time']),
                raw=msg
            )
            await self.callback(OPEN_INTEREST, o, timestamp)
            self._open_interest_cache[pair] = oi

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []
        if self.address:
            ret = super().connect()
        PollCls = HTTPConcurrentPoll if self.concurrent_http else HTTPPoll
        for chan in set(self.subscription):
            if chan == 'open_interest':
                addrs = [f"{self.rest_endpoint}/openInterest?symbol={pair}" for pair in self.subscription[chan]]
                ret.append((PollCls(addrs, self.id, delay=60.0, sleep=self.open_interest_interval, proxy=self.http_proxy), self.subscribe, self.message_handler, self.authenticate))
        return ret

    async def _account_update(self, msg: dict, timestamp: float):
        """
        {
        "e": "ACCOUNT_UPDATE",                // Event Type
        "E": 1564745798939,                   // Event Time
        "T": 1564745798938 ,                  // Transaction
        "a":                                  // Update Data
            {
            "m":"ORDER",                      // Event reason type
            "B":[                             // Balances
                {
                "a":"USDT",                   // Asset
                "wb":"122624.12345678",       // Wallet Balance
                "cw":"100.12345678",          // Cross Wallet Balance
                "bc":"50.12345678"            // Balance Change except PnL and Commission
                },
                {
                "a":"BUSD",
                "wb":"1.00000000",
                "cw":"0.00000000",
                "bc":"-49.12345678"
                }
            ],
            "P":[
                {
                "s":"BTCUSDT",            // Symbol
                "pa":"0",                 // Position Amount
                "ep":"0.00000",            // Entry Price
                "cr":"200",               // (Pre-fee) Accumulated Realized
                "up":"0",                     // Unrealized PnL
                "mt":"isolated",              // Margin Type
                "iw":"0.00000000",            // Isolated Wallet (if isolated position)
                "ps":"BOTH"                   // Position Side
                }，
                {
                    "s":"BTCUSDT",
                    "pa":"20",
                    "ep":"6563.66500",
                    "cr":"0",
                    "up":"2850.21200",
                    "mt":"isolated",
                    "iw":"13200.70726908",
                    "ps":"LONG"
                },
                {
                    "s":"BTCUSDT",
                    "pa":"-10",
                    "ep":"6563.86000",
                    "cr":"-45.04000000",
                    "up":"-1423.15600",
                    "mt":"isolated",
                    "iw":"6570.42511771",
                    "ps":"SHORT"
                }
            ]
            }
        }
        """
        for balance in msg['a']['B']:
            await self.callback(BALANCES,
                                feed=self.id,
                                symbol=balance['a'],
                                timestamp=self.timestamp_normalize(msg['E']),
                                receipt_timestamp=timestamp,
                                wallet_balance=Decimal(balance['wb']))
        for position in msg['a']['P']:
            await self.callback(POSITIONS,
                                feed=self.id,
                                symbol=self.exchange_symbol_to_std_symbol(position['s']),
                                timestamp=self.timestamp_normalize(msg['E']),
                                receipt_timestamp=timestamp,
                                position_amount=Decimal(position['pa']),
                                entry_price=Decimal(position['ep']),
                                unrealised_pnl=Decimal(position['up']))

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Handle REST endpoint messages first
        if 'openInterest' in msg:
            coro = self._open_interest(msg, timestamp)
            if self.concurrent_http:
                return create_task(coro)
            return await coro

        # Handle account updates from User Data Stream
        if self.requires_authentication:
            msg_type = msg.get('e')
            if msg_type == 'ACCOUNT_UPDATE':
                await self._account_update(msg, timestamp)
            return

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
        elif msg['e'] == 'kline':
            await self._candle(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

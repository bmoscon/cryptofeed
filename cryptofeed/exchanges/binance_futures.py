'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
from typing import Tuple, Dict

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BALANCES, BINANCE_FUTURES, BUY, FUNDING, LIMIT, LIQUIDATIONS, MARKET, OPEN_INTEREST, ORDER_INFO, POSITIONS, SELL
from cryptofeed.exchanges.binance import Binance
from cryptofeed.exchanges.mixins.binance_rest import BinanceFuturesRestMixin
from cryptofeed.types import Balance, OpenInterest, OrderInfo, Position

LOG = logging.getLogger('feedhandler')


class BinanceFutures(Binance, BinanceFuturesRestMixin):
    id = BINANCE_FUTURES
    websocket_endpoints = [WebsocketEndpoint('wss://fstream.binance.com', sandbox='wss://stream.binancefuture.com', options={'compression': None})]
    rest_endpoints = [RestEndpoint('https://fapi.binance.com', sandbox='https://testnet.binancefuture.com', routes=Routes('/fapi/v1/exchangeInfo', l2book='/fapi/v1/depth?symbol={}&limit={}', authentication='/fapi/v1/listenKey', open_interest='/fapi/v1/openInterest?symbol={}'))]

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
        open_interest_interval: float
            time in seconds between open_interest polls
        """
        super().__init__(**kwargs)
        self.open_interest_interval = open_interest_interval

    def _connect_rest(self):
        ret = []
        for chan in set(self.subscription):
            if chan == 'open_interest':
                addrs = [self.rest_endpoints[0].route('open_interest', sandbox=self.sandbox).format(pair) for pair in self.subscription[chan]]
                ret.append((HTTPPoll(addrs, self.id, delay=60.0, sleep=self.open_interest_interval, proxy=self.http_proxy), self.subscribe, self.message_handler, self.authenticate))
        return ret

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
            b = Balance(
                self.id,
                balance['a'],
                Decimal(balance['wb']),
                None,
                raw=msg)
            await self.callback(BALANCES, b, timestamp)
        for position in msg['a']['P']:
            p = Position(
                self.id,
                self.exchange_symbol_to_std_symbol(position['s']),
                Decimal(position['pa']),
                Decimal(position['ep']),
                position['ps'].lower(),
                Decimal(position['up']),
                self.timestamp_normalize(msg['E']),
                raw=msg)
            await self.callback(POSITIONS, p, timestamp)

    async def _order_update(self, msg: dict, timestamp: float):
        """
        {
            "e":"ORDER_TRADE_UPDATE",     // Event Type
            "E":1568879465651,            // Event Time
            "T":1568879465650,            // Transaction Time
            "o":
            {
                "s":"BTCUSDT",              // Symbol
                "c":"TEST",                 // Client Order Id
                // special client order id:
                // starts with "autoclose-": liquidation order
                // "adl_autoclose": ADL auto close order
                "S":"SELL",                 // Side
                "o":"TRAILING_STOP_MARKET", // Order Type
                "f":"GTC",                  // Time in Force
                "q":"0.001",                // Original Quantity
                "p":"0",                    // Original Price
                "ap":"0",                   // Average Price
                "sp":"7103.04",             // Stop Price. Please ignore with TRAILING_STOP_MARKET order
                "x":"NEW",                  // Execution Type
                "X":"NEW",                  // Order Status
                "i":8886774,                // Order Id
                "l":"0",                    // Order Last Filled Quantity
                "z":"0",                    // Order Filled Accumulated Quantity
                "L":"0",                    // Last Filled Price
                "N":"USDT",             // Commission Asset, will not push if no commission
                "n":"0",                // Commission, will not push if no commission
                "T":1568879465651,          // Order Trade Time
                "t":0,                      // Trade Id
                "b":"0",                    // Bids Notional
                "a":"9.91",                 // Ask Notional
                "m":false,                  // Is this trade the maker side?
                "R":false,                  // Is this reduce only
                "wt":"CONTRACT_PRICE",      // Stop Price Working Type
                "ot":"TRAILING_STOP_MARKET",    // Original Order Type
                "ps":"LONG",                        // Position Side
                "cp":false,                     // If Close-All, pushed with conditional order
                "AP":"7476.89",             // Activation Price, only puhed with TRAILING_STOP_MARKET order
                "cr":"5.0",                 // Callback Rate, only puhed with TRAILING_STOP_MARKET order
                "rp":"0"                            // Realized Profit of the trade
            }
        }
        """
        oi = OrderInfo(
            self.id,
            self.exchange_symbol_to_std_symbol(msg['o']['s']),
            str(msg['o']['i']),
            BUY if msg['o']['S'].lower() == 'buy' else SELL,
            msg['o']['x'],
            LIMIT if msg['o']['o'].lower() == 'limit' else MARKET if msg['o']['o'].lower() == 'market' else None,
            Decimal(msg['o']['ap']) if not Decimal.is_zero(Decimal(msg['o']['ap'])) else None,
            Decimal(msg['o']['q']),
            Decimal(msg['o']['q']) - Decimal(msg['o']['z']),
            self.timestamp_normalize(msg['E']),
            raw=msg
        )
        await self.callback(ORDER_INFO, oi, timestamp)

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Handle REST endpoint messages first
        if 'openInterest' in msg:
            return await self._open_interest(msg, timestamp)

        # Handle account updates from User Data Stream
        if self.requires_authentication:
            msg_type = msg.get('e')
            if msg_type == 'ACCOUNT_UPDATE':
                await self._account_update(msg, timestamp)
            elif msg_type == 'ORDER_TRADE_UPDATE':
                await self._order_update(msg, timestamp)
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

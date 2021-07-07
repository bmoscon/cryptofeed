'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
import time
from typing import List, Tuple, Callable, Dict

from yapic import json

from cryptofeed.connection import AsyncConnection, HTTPPoll
from cryptofeed.defines import BINANCE_FUTURES, OPEN_INTEREST, ACCOUNT_UPDATE, ORDER_INFO, BUY, SELL
from cryptofeed.exchange.binance import Binance
from cryptofeed.standards import timestamp_normalize

LOG = logging.getLogger('feedhandler')


class BinanceFutures(Binance):
    id = BINANCE_FUTURES
    valid_depths = [5, 10, 20, 50, 100, 500, 1000]
    symbol_endpoint = 'https://fapi.binance.com/fapi/v1/exchangeInfo'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        base, info = super()._parse_symbol_data(data, symbol_separator)
        add = {}
        for symbol, orig in base.items():
            if "_" in orig:
                continue
            add[f"{symbol}{symbol_separator}PINDEX"] = f"p{orig}"
        base.update(add)
        return base, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # overwrite values previously set by the super class Binance
        self.ws_endpoint = 'wss://fstream.binance.com'
        self.rest_endpoint = 'https://fapi.binance.com/fapi/v1'
        self.address = self._address()

    def _check_update_id(self, pair: str, msg: dict) -> Tuple[bool, bool]:
        skip_update = False
        forced = not self.forced[pair]

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
        return skip_update, forced

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
                                timestamp=timestamp_normalize(self.id, msg['time']),
                                receipt_timestamp=time.time()
                                )
            self.open_interest[pair] = oi

    def connect(self) -> List[Tuple[AsyncConnection, Callable[[None], None], Callable[[str, float], None]]]:
        ret = []
        if self.address:
            ret = super().connect()

        for chan in set(self.subscription):
            if chan == 'open_interest':
                addrs = [f"{self.rest_endpoint}/openInterest?symbol={pair}" for pair in self.subscription[chan]]
                ret.append((HTTPPoll(addrs, self.id, delay=60.0, sleep=1.0), self.subscribe, self.message_handler, self.authenticate))
        return ret

    async def message_handler(self, msg: str, conn: AsyncConnection, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

        # Handle REST endpoint messages first
        if 'openInterest' in msg:
            await self._open_interest(msg, timestamp)
            return

        # Combined stream events are wrapped as follows: {"stream":"<streamName>","data":<rawPayload>}
        # streamName is of format <symbol>@<channel>
        if '@' in msg['stream']:
            pair, _ = msg['stream'].split('@', 1)
            pair = pair.upper()

        msg = msg['data']
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
        elif msg_type == "ACCOUNT_UPDATE":
            await self._account_update(msg, timestamp)
        elif msg_type == "ORDER_TRADE_UPDATE":
            await self._order(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

    async def _order(self, msg: dict, timestamp: float):
        """
        {

          "e":"ORDER_TRADE_UPDATE",     // Event Type
          "E":1568879465651,            // Event Time
          "T":1568879465650,            // Transaction Time
          "o":{
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

        status = msg['o']['x']
        data = {}
        data.update({'clOrdId': msg['o']['c']})
        data.update({'fillPx': Decimal(msg['o']['L'])})
        data.update({'fillSz': Decimal(msg['o']['l'])})
        if 'n' in msg['o']:
            data.update({'fillFee': Decimal(msg['o']['n'])})
            data.update({'fillFeeCcy': msg['o']['N']})
        else:
            data.update({'fillFee': Decimal(0)})
            data.update({'fillFeeCcy': ''})

        await self.callback(ORDER_INFO,
                            feed=self.id,
                            symbol=self.exchange_symbol_to_std_symbol(msg['o']['s'].upper()),
                            status=status,
                            order_id=msg['o']['i'],
                            side=BUY if msg['o']['S'].lower() == 'buy' else SELL,
                            order_type=msg['o']['ot'],
                            timestamp=msg['E'],
                            receipt_timestamp=timestamp,
                            **data
                            )

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
        await self.callback(ACCOUNT_UPDATE,
                            feed=self.id,
                            timestamp=msg['E'],
                            receipt_timestamp=timestamp
                            )

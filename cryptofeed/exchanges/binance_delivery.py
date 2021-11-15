'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging

from yapic import json

from cryptofeed.defines import BALANCES, BINANCE_DELIVERY, BUY, FUNDING, LIMIT, LIQUIDATIONS, MARKET, OPEN_INTEREST, ORDER_INFO, POSITIONS, SELL
from cryptofeed.exchanges.binance import Binance
from cryptofeed.exchanges.mixins.binance_rest import BinanceDeliveryRestMixin
from cryptofeed.types import Balance, OrderInfo, Position


LOG = logging.getLogger('feedhandler')


class BinanceDelivery(Binance, BinanceDeliveryRestMixin):
    id = BINANCE_DELIVERY
    symbol_endpoint = 'https://dapi.binance.com/dapi/v1/exchangeInfo'
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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # overwrite values previously set by the super class Binance
        self.ws_endpoint = 'wss://dstream.binance.com'
        self.rest_endpoint = 'https://dapi.binance.com/dapi/v1'
        self.address = self._address()
        self.ws_defaults['compression'] = None

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

    async def _account_update(self, msg: dict, timestamp: float):
        """
        {
        "e": "ACCOUNT_UPDATE",            // Event Type
        "E": 1564745798939,               // Event Time
        "T": 1564745798938 ,              // Transaction
        "i": "SfsR",                      // Account Alias
        "a":                              // Update Data
            {
            "m":"ORDER",                  // Event reason type
            "B":[                         // Balances
                {
                "a":"BTC",                // Asset
                "wb":"122624.12345678",   // Wallet Balance
                "cw":"100.12345678"       // Cross Wallet Balance
                },
                {
                "a":"ETH",
                "wb":"1.00000000",
                "cw":"0.00000000"
                }
            ],
            "P":[
                {
                "s":"BTCUSD_200925",      // Symbol
                "pa":"0",                 // Position Amount
                "ep":"0.0",               // Entry Price
                "cr":"200",               // (Pre-fee) Accumulated Realized
                "up":"0",                 // Unrealized PnL
                "mt":"isolated",          // Margin Type
                "iw":"0.00000000",        // Isolated Wallet (if isolated position)
                "ps":"BOTH"               // Position Side
                },
                {
                    "s":"BTCUSD_200925",
                    "pa":"20",
                    "ep":"6563.6",
                    "cr":"0",
                    "up":"2850.21200000",
                    "mt":"isolated",
                    "iw":"13200.70726908",
                    "ps":"LONG"
                },
                {
                    "s":"BTCUSD_200925",
                    "pa":"-10",
                    "ep":"6563.8",
                    "cr":"-45.04000000",
                    "up":"-1423.15600000",
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
            "E":1591274595442,            // Event Time
            "T":1591274595453,            // Transaction Time
            "i":"SfsR",                   // Account Alias
            "o":
            {
                "s":"BTCUSD_200925",        // Symbol
                "c":"TEST",                 // Client Order Id
                // special client order id:
                // starts with "autoclose-": liquidation order
                // "adl_autoclose": ADL auto close order
                "S":"SELL",                 // Side
                "o":"TRAILING_STOP_MARKET", // Order Type
                "f":"GTC",                  // Time in Force
                "q":"2",                    // Original Quantity
                "p":"0",                    // Original Price
                "ap":"0",                   // Average Price
                "sp":"9103.1",              // Stop Price. Please ignore with TRAILING_STOP_MARKET order
                "x":"NEW",                  // Execution Type
                "X":"NEW",                  // Order Status
                "i":8888888,                // Order Id
                "l":"0",                    // Order Last Filled Quantity
                "z":"0",                    // Order Filled Accumulated Quantity
                "L":"0",                    // Last Filled Price
                "ma": "BTC",                // Margin Asset
                "N":"BTC",                  // Commission Asset of the trade, will not push if no commission
                "n":"0",                    // Commission of the trade, will not push if no commission
                "T":1591274595442,          // Order Trade Time
                "t":0,                      // Trade Id
                "rp": "0",                  // Realized Profit of the trade
                "b":"0",                    // Bid quantity of base asset
                "a":"0",                    // Ask quantity of base asset
                "m":false,                  // Is this trade the maker side?
                "R":false,                  // Is this reduce only
                "wt":"CONTRACT_PRICE",      // Stop Price Working Type
                "ot":"TRAILING_STOP_MARKET",// Original Order Type
                "ps":"LONG",                // Position Side
                "cp":false,                 // If Close-All, pushed with conditional order
                "AP":"9476.8",              // Activation Price, only puhed with TRAILING_STOP_MARKET order
                "cr":"5.0",                 // Callback Rate, only puhed with TRAILING_STOP_MARKET order
                "pP": false                 // If conditional order trigger is protected
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

    async def message_handler(self, msg: str, conn, timestamp: float):
        msg = json.loads(msg, parse_float=Decimal)

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
        elif msg_type == 'kline':
            await self._candle(msg, timestamp)
        else:
            LOG.warning("%s: Unexpected message received: %s", self.id, msg)

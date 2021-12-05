'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

from yapic import json

#import new defines
from cryptofeed.defines import (BALANCES, BUY, CANCEL_ORDER, CANDLES, DELETE, 
    FILL_OR_KILL, GET, GOOD_TIL_CANCELED, IMMEDIATE_OR_CANCEL, LIMIT, MARKET, 
    ORDERS, ORDER_STATUS, PLACE_ORDER, POSITIONS, POST, SELL, TRADES, FEED, 
    SYMBOL, BID, ASK, L2_BOOK, TICKER, BID_PRICE, BID_AMOUNT, ASK_PRICE, ASK_AMOUNT, 
    START, END, LIMIT, TIMESTAMP, SIDE, BUY, AMOUNT, PRICE)
from cryptofeed.exchange import RestExchange
from cryptofeed.types import Candle
#import the new helper classes
from cryptofeed.util.payloads import Payload
from cryptofeed.util.keymapping import Keymap, access_route


LOG = logging.getLogger('feedhandler')


class BinanceRestMixin(RestExchange):
    rest_channels = [
        TICKER, 
        L2_BOOK, 
        TRADES]
    '''
    basic request data is defined at class level, minimalizes the need to pass
    numerous parameters. 
    ''' 
    api_endpoints = {
        TICKER      : 'https://api.binance.com/api/v3/ticker/bookTicker',
        L2_BOOK     : 'https://api.binance.com/api/v3/depth',
        TRADES      : 'https://api.binance.com/api/v3/aggTrades',
    }
    methods = {
        TICKER : GET,
        L2_BOOK : GET,
        TRADES : GET,
    }
    payload_as_params = {
        TICKER : True, 
        L2_BOOK : True,
        TRADES : True,
    }
    

    '''all functions only require the instialization of a Payload and Keymap'''
    async def ticker(self, symbol: str, retry=None, retry_wait=10):
        payload = Payload({
        SYMBOL : {'symbol' : None}
        })
        keymap = Keymap({
            SYMBOL : symbol,
            FEED : self.id,
            BID : access_route('bidPrice', Decimal),
            ASK : access_route('askPrice', Decimal)
        })
        return await self._rest_ticker(payload, keymap, symbol, retry, retry_wait)
    
    async def l2_book(self, symbol: str, retry=None, retry_wait=10):
        payload = Payload({
            SYMBOL : {'symbol' : None},
        })
        keymap = Keymap({
            BID_PRICE   : access_route('bids', slice(None), 0, Decimal),
            BID_AMOUNT  : access_route('bids', slice(None), 1, Decimal),
            ASK_PRICE   : access_route('asks', slice(None), 0, Decimal),
            ASK_AMOUNT  : access_route('asks', slice(None), 1, Decimal),
        })
        return await self._rest_l2_book(payload, keymap, symbol, limit, retry, retry_wait)
    
    async def trades(self, symbol, limit=None, start= None, end=None, retry=None, retry_wait=None):
        payload = Payload({
            SYMBOL : {'symbol' : None},
            START : {'startTime' : None},
            END :   {'endTime' : None}, 
        })
        keymap = Keymap({
            TIMESTAMP   : access_route(slice(None), 'T', self.exchange_ts_to_std_ts),
            SYMBOL      : symbol,
            ID          : access_route(slice(None), 'a'),
            FEED        : self.id,
            SIDE        : access_route(slice(None), 'm', lambda x : BUY if x is True else SELL),
            AMOUNT      : access_route(slice(None), 'q', Decimal),
            PRICE       : access_route(slice(None), 'p', Decimal)
            
        })
        return await self._rest_trades(payload, keymap, symbol, 
                            limit, start, end, 60*60, retry=retry, 
                            retry_wait=retry_wait)


class BinanceFuturesRestMixin(BinanceRestMixin):
    api = 'https://fapi.binance.com/fapi/v1/'
    rest_channels = (
        TRADES, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, ORDERS, POSITIONS
    )

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, time_in_force=None):
        data = await super().place_order(symbol, side, order_type, amount, price=price, time_in_force=time_in_force, test=False)
        return data

    async def balances(self):
        data = await self._request(GET, 'account', auth=True, api='https://fapi.binance.com/fapi/v2/')
        return data['assets']

    async def positions(self):
        data = await self._request(GET, 'account', auth=True, api='https://fapi.binance.com/fapi/v2/')
        return data['positions']


class BinanceDeliveryRestMixin(BinanceRestMixin):
    api = 'https://dapi.binance.com/dapi/v1/'
    rest_channels = (
        TRADES, ORDER_STATUS, CANCEL_ORDER, PLACE_ORDER, BALANCES, ORDERS, POSITIONS
    )

    async def place_order(self, symbol: str, side: str, order_type: str, amount: Decimal, price=None, time_in_force=None):
        data = await super().place_order(symbol, side, order_type, amount, price=price, time_in_force=time_in_force, test=False)
        return data

    async def balances(self):
        data = await self._request(GET, 'account', auth=True)
        return data['assets']

    async def positions(self):
        data = await self._request(GET, 'account', auth=True)
        return data['positions']


class BinanceUSRestMixin(BinanceRestMixin):
    api = 'https://api.binance.us/api/v3/'
    rest_channels = (
        TRADES
    )

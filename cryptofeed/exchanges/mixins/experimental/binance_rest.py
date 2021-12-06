'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
from cryptofeed.defines import (BUY, GET, SELL, TRADES, FEED, SYMBOL, BID, ASK, L2_BOOK, TICKER, 
                                BID_PRICE, BID_AMOUNT, ASK_PRICE, ASK_AMOUNT, START, END, ID, TIMESTAMP, 
                                SIDE, BUY, AMOUNT, PRICE)
from cryptofeed.exchange import RestExchange
from cryptofeed.util.payloads import Payload
from cryptofeed.util.keymapping import Keymap, access_route


LOG = logging.getLogger('feedhandler')

class BinanceRestMixin(RestExchange):
    rest_channels = [
        TICKER, 
        L2_BOOK, 
        TRADES
        ]
    api_calls = {
        TICKER      : (GET, 'https://api.binance.com/api/v3/ticker/bookTicker'),
        L2_BOOK     : (GET, 'https://api.binance.com/api/v3/depth'),
        TRADES      : (GET, 'https://api.binance.com/api/v3/aggTrades'),
    }    

    async def ticker(self, symbol: str):
        payload = Payload({
        SYMBOL : {'symbol' : None}
        })
        keymap = Keymap({
            SYMBOL : symbol,
            FEED : self.id,
            BID : access_route('bidPrice', Decimal),
            ASK : access_route('askPrice', Decimal)
        })
        return await self._rest_ticker(payload, keymap, symbol)
    
    async def l2_book(self, symbol: str):
        payload = Payload({
            SYMBOL : {'symbol' : None},
        })
        keymap = Keymap({
            BID_PRICE   : access_route('bids', slice(None), 0, Decimal),
            BID_AMOUNT  : access_route('bids', slice(None), 1, Decimal),
            ASK_PRICE   : access_route('asks', slice(None), 0, Decimal),
            ASK_AMOUNT  : access_route('asks', slice(None), 1, Decimal),
        })
        return await self._rest_l2_book(payload, keymap, symbol)
    
    async def trades(self, symbol, start= None, end=None):
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
        return await self._rest_trades(payload, keymap, symbol, start, end, 60*60)
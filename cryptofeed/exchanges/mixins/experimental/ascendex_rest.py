'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import logging
#import new defines
from cryptofeed.defines import (BUY, GET, SELL, TRADES, FEED, SYMBOL, BID, ASK, L2_BOOK, TICKER, 
                                BID_PRICE, BID_AMOUNT, ASK_PRICE, ASK_AMOUNT, START, END, ID, TIMESTAMP, 
                                SIDE, BUY, AMOUNT, PRICE)
from cryptofeed.exchange import RestExchange
#import the new helper classes
from cryptofeed.util.payloads import Payload
from cryptofeed.util.keymapping import Keymap, access_route

LOG = logging.getLogger('feedhandler')

class AscenddexMixin(RestExchange):
    rest_channels = [
        TICKER, 
        L2_BOOK, 
        TRADES
        ]
    '''
    basic request data is defined at class level, minimalizes the need to pass
    numerous parameters. 
    ''' 
    api_calls = {
        TICKER      : (GET, "https://ascendex.com/api/pro/v1/spot/ticker"),
        L2_BOOK     : (GET, 'https://ascendex.com/api/pro/v1/depth'),
        TRADES      : (GET, 'https://ascendex.com/api/pro/v1/trades'),
    }    

    '''all functions should only require the instialization of a Payload and Keymap'''
    async def ticker(self, symbol: str):
        payload = Payload({
        SYMBOL : {'symbol' : None}
        })
        keymap = Keymap({
            SYMBOL : symbol,
            FEED : self.id,
            BID : access_route('data', 'bid', 0, Decimal),
            ASK : access_route('data', 'ask', 0, Decimal)
        })
        return await self._rest_ticker(payload, keymap, symbol)
    
    async def l2_book(self, symbol: str):
        payload = Payload({
            SYMBOL : {'symbol' : None},
        })
        keymap = Keymap({
            BID_PRICE   : access_route('data', 'data', 'bids', slice(None), 0, Decimal),
            BID_AMOUNT  : access_route('data', 'data', 'bids', slice(None), 1, Decimal),
            ASK_PRICE   : access_route('data', 'data', 'asks', slice(None), 0, Decimal),
            ASK_AMOUNT  : access_route('data', 'data', 'asks', slice(None), 1, Decimal),
        })
        return await self._rest_l2_book(payload, keymap, symbol)
    
    async def trades(self, symbol : str):
        payload = Payload({
            SYMBOL : {'symbol' : None},
            START : None,
            END :   None, 
        })
        keymap = Keymap({
            TIMESTAMP   : access_route('data', 'data', slice(None), 'ts', self.exchange_ts_to_std_ts),
            SYMBOL      : symbol,
            ID          : None, #does seq_num counts as an id?
            FEED        : self.id,
            SIDE        : access_route('data', 'data', slice(None), 'bm', lambda x : BUY if x is True else SELL),
            AMOUNT      : access_route('data', 'data', slice(None), 'q', Decimal),
            PRICE       : access_route('data', 'data', slice(None), 'p', Decimal)
            
        })
        return await self._rest_trades(payload, keymap, symbol)

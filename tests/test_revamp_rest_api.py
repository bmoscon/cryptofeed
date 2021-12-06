import asyncio
from inspect import getfullargspec
from typing import Dict, List, Union
import cryptofeed
import time
from decimal import Decimal
from cryptofeed.defines import BID, ASK, BUY, SELL, SYMBOL, TIMESTAMP, ID, FEED, SIDE, AMOUNT, PRICE
from cryptofeed.exchange import Exchange, RestExchange
from cryptofeed.exchanges import EXPERIMENTAL_MAP
from cryptofeed.exchanges.kraken import Kraken
from cryptofeed.symbols import Symbol
from logging import getLogger
'''
run tests to see if all calls return expected results
'''


# use something on all exchanges.
test_symbol = 'BTC-USDT' 
#??? as an idea: pick randomly from exchange.info()['symbols'] ???

def check_timestamp(ts, mini=1312149600, maxi=None):
    '''
    Note: 1312149600 is the founding month of the oldest exchange which is still in existance - bitstamp.
    '''
    if maxi is None:
        maxi = time.time()
    return mini < ts < time.time()

async def check_l2_book(exchange : RestExchange):
    l2_book = await exchange.l2_book(test_symbol)
    assert isinstance(l2_book, dict)
    assert isinstance(l2_book[BID], list)
    assert isinstance(l2_book[ASK], list)
    assert all(isinstance(x, dict) for x in l2_book[BID])
    assert all(isinstance(x, dict) for x in l2_book[ASK])
    assert all(isinstance(next(iter(a.values())), Decimal) and isinstance(next(iter(a.keys())), Decimal) for a in l2_book[BID])
    assert all(isinstance(next(iter(a.values())), Decimal) and isinstance(next(iter(a.keys())), Decimal) for a in l2_book[ASK])
    assert all(next(iter(l2_book[BID][i].values())) < next(iter(l2_book[BID][i].values())) for i in range(len(l2_book[BID])-1))
    assert all(next(iter(l2_book[ASK][i].values())) < next(iter(l2_book[ASK][i].values())) for i in range(len(l2_book[ASK])-1))


async def check_ticker(exchange : RestExchange):
    ticker = await exchange.ticker(test_symbol)
    assert isinstance(ticker, dict)
    assert tuple(ticker.keys()) == (SYMBOL, FEED, BID, ASK)
    assert ticker[SYMBOL] == test_symbol
    assert ticker[FEED] == exchange.id
    assert isinstance(ticker[BID], Decimal)
    assert isinstance(ticker[ASK], Decimal)

async def check_trades(exchange : RestExchange):
    trades = await exchange.trades(test_symbol)
    assert isinstance(trades, list)
    assert all(tuple(x.keys()) == (TIMESTAMP, SYMBOL, ID, FEED, SIDE, AMOUNT, PRICE) for x in trades)
    assert all(x[SYMBOL] == test_symbol for x in trades)
    assert all(x[FEED] == exchange.id for x in trades)
    if not isinstance(trades[0][TIMESTAMP], type(None)):
        assert all((isinstance(x[TIMESTAMP], float) and check_timestamp(x[TIMESTAMP])) for x in trades)
        assert all(isinstance(x[ID], (int, type(None))) for x in trades)
        assert all(x[SIDE] in [BUY, SELL, None] for x in trades)
        assert all(isinstance(x[AMOUNT], (Decimal, type(None))) for x in trades)
        assert all(isinstance(x[PRICE], (Decimal, type(None))) for x in trades)
    if len(trades) > 1:
        assert all(trades[i][TIMESTAMP] <= trades[i + 1][TIMESTAMP] for i in range(len(trades)-1))

async def main():
    for ex in EXPERIMENTAL_MAP.values():
        ex = ex()
        await check_trades(ex)
        await check_ticker(ex)
        await check_l2_book(ex)
    
loop = asyncio.get_event_loop()
loop.run_until_complete(main())
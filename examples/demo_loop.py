'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import datetime
from collections import defaultdict
import functools

from cryptofeed import FeedHandler
from cryptofeed.callback import DeribitTickerCallback
from cryptofeed.defines import BID, ASK, TRADES, L2_BOOK, PERPETURAL, OPTION, FUTURE, ANY, TICKER, USER_TRADES
from cryptofeed.exchanges import Deribit
from cryptofeed.util.instrument import get_instrument_type

async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp, **kwargs):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"Timestamp: {get_time_from_timestamp(timestamp * 1000)} Rx: {get_time_from_timestamp(receipt_timestamp * 1000)} (+{receipt_timestamp * 1000 - timestamp * 1000}) Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")

async def ticker(feed, symbol, bid, bid_amount, ask, ask_amount, timestamp, receipt_timestamp, bid_iv, ask_iv, delta, gamma, rho, theta, vega, mark_price, mark_iv, underlying_index, underlying_price):
    print(f'Timestamp: {get_time_from_timestamp(timestamp * 1000)} Feed: {feed} Pair: {symbol} Bid: {bid} Bid amount: {bid_amount} Ask: {ask} Ask amount: {ask_amount} Bid iv: {bid_iv} Ask iv: {ask_iv} Delta: {delta} Gamma: {gamma} Rho: {rho} Theta: {theta} Vega: {vega} Mark price: {mark_price} Mark iv: {mark_iv}')

async def perp_ticker(feed, symbol, bid, bid_amount, ask, ask_amount, timestamp, receipt_timestamp):
    print(f'Timestamp: {get_time_from_timestamp(timestamp * 1000)} Feed: {feed} Pair: {symbol} Bid: {bid} Bid amount: {bid_amount} Ask: {ask} Ask amount: {ask_amount}')

async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {get_time_from_timestamp(timestamp * 1000)} Feed: {feed} Pair: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])} {book}')

async def do_periodically_at(hour, minute, second, periodic_function):
    while True:
        t = datetime.datetime.today()
        future = datetime.datetime(t.year, t.month, t.day, hour, minute, second)
        if t >= future:
            print(f'{t} > {future}')
            future += datetime.timedelta(days=1)
        delay = (future - t).total_seconds()
        h = (int)(delay/3600)
        m = int((delay-h*3600)/60)
        s = (int)(delay%60)
        print(f'Waiting {h} hours {m} minutes {s} seconds to execute periodic function')
        await asyncio.sleep(delay)
        await periodic_function()

def get_new_subscription():
    symbols = Deribit.get_instruments()
    new_subscription = defaultdict(set)
    for symbol in symbols:
        for feed_type in subscription[get_instrument_type(symbol)]:
            new_subscription[feed_type].add(symbol)
    return new_subscription

async def subscribe_to_new_subscription(deribit):
    await deribit.update_subscription(subscription=get_new_subscription())
    # wait a little to let the clock tick on
    await asyncio.sleep(5)

def get_time_from_timestamp(timestamp):
    s, ms = divmod(timestamp, 1000)
    return '%s.%03d' % (datetime.datetime.utcfromtimestamp(s).strftime('%H:%M:%S'), ms)

subscription = {
    PERPETURAL: [],
    OPTION: [],
    FUTURE: []

    # PERPETURAL: [TICKER, TRADES],
    # OPTION: [TICKER, L2_BOOK],
    # FUTURE: [TICKER]

    # PERPETURAL: [TICKER, TRADES],
    # OPTION: [TICKER, TRADES, L2_BOOK],
    # FUTURE: [TICKER]
}

other_subscription = {
    TRADES: [FUTURE, OPTION],
    USER_TRADES: [ANY],
}

callbacks = {
    L2_BOOK: book, 
    TRADES: trade, 
    TICKER: DeribitTickerCallback(callbacks={OPTION: ticker, PERPETURAL: perp_ticker}),
    USER_TRADES: trade,
}

def main():
    f = FeedHandler(config="config.yaml")
    all_subscription = get_new_subscription()
    for key, value in other_subscription.items():
        all_subscription[key].update(value)
    print(all_subscription)
    deribit = Deribit(config="config.yaml", max_depth=1, subscription=all_subscription, callbacks=callbacks)
    f.add_feed(deribit)
    f.run(start_loop=True, tasks=[do_periodically_at(8, 1, 1, functools.partial(subscribe_to_new_subscription, deribit))])
    
if __name__ == '__main__':
    main()

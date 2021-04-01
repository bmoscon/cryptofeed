'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from multiprocessing import Process
import asyncio
from decimal import Decimal
import datetime
from collections import defaultdict
import functools

from yapic import json

from cryptofeed import FeedHandler
from cryptofeed.backends.zmq import DeribitBookZMQ, DeribitTickerZMQ, DeribitTradeZMQ
from cryptofeed.defines import BID, ASK, TRADES, L2_BOOK, PERPETURAL, OPTION, FUTURE, ANY, TICKER, USER_TRADES
from cryptofeed.exchanges import Deribit
from cryptofeed.util.instrument import get_instrument_type


def receiver(port):
    import zmq
    addr = 'tcp://127.0.0.1:{}'.format(port)
    ctx = zmq.Context.instance()
    s = ctx.socket(zmq.SUB)
    # empty subscription for all data, could be book for just book data, etc
    s.setsockopt(zmq.SUBSCRIBE, b'')

    s.bind(addr)
    while True:
        data = s.recv_string()
        key, msg = data.split(" ", 1)
        print(key)
        print(json.loads(msg))

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
    L2_BOOK: DeribitBookZMQ(port=5678), 
    TRADES: DeribitTradeZMQ(port=5678), 
    TICKER: DeribitTickerZMQ(port=5678),
    # USER_TRADES: trade,
}

def main():
    try:
        p = Process(target=receiver, args=(5678,))

        p.start()

        f = FeedHandler(config="config.yaml")
        all_subscription = get_new_subscription()
        for key, value in other_subscription.items():
            all_subscription[key].update(value)
        print(all_subscription)
        deribit = Deribit(config="config.yaml", max_depth=1, subscription=all_subscription, callbacks=callbacks)
        f.add_feed(deribit)
        # f.add_feed(Deribit(max_depth=1, channels=[L2_BOOK], symbols=['BTC-PERPETUAL'], callbacks={L2_BOOK: BookZMQ(port=5678)}))
        # f.add_feed(Coinbase(channels=[TICKER], symbols=['BTC-USD'], callbacks={TICKER: TickerZMQ(port=5678)}))
        f.run(start_loop=True, tasks=[do_periodically_at(8, 1, 1, functools.partial(subscribe_to_new_subscription, deribit))])

    finally:
        p.terminate()


if __name__ == '__main__':
    main()

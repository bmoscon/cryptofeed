'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.aggregate import CustomAggregate
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


async def callback(data):
    print(data)


def custom_agg(data, trade, receipt):
    if trade.symbol not in data:
        data[trade.symbol] = {'min': trade.price, 'max': trade.price}
    else:
        if trade.price > data[trade.symbol]['max']:
            data[trade.symbol]['max'] = trade.price
        elif trade.price < data[trade.symbol]['min']:
            data[trade.symbol]['min'] = trade.price


def init(data):
    """
    called at start of each new interval. We just need to clear the
    internal state
    """
    data.clear()


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: CustomAggregate(callback, window=30, init=init, aggregator=custom_agg)}))

    f.run()


if __name__ == '__main__':
    main()

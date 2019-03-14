'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import Callback
from cryptofeed.backends.aggregate import CustomAggregate

from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import TRADES


async def callback(data=None):
    print(data)


def custom_agg(data, feed=None, pair=None, side=None, amount=None, price=None, order_id=None, timestamp=None):
    if pair not in data:
        data[pair] = {'min': price, 'max': price}
    else:
        if price > data[pair]['max']:
            data[pair]['max'] = price
        elif price < data[pair]['min']:
            data[pair]['min'] = price


def init(data):
    """
    called at start of each new interval. We just need to clear the
    internal state
    """
    data = {}


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[TRADES], callbacks={TRADES: CustomAggregate(Callback(callback), window=30, init=init, aggregator=custom_agg)}))

    f.run()


if __name__ == '__main__':
    main()

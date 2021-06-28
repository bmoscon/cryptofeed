'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.aggregate import CustomAggregate
from cryptofeed.callback import Callback
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


async def callback(data=None):
    print(data)


def custom_agg(data, feed=None, symbol=None, side=None, amount=None, price=None, order_id=None, timestamp=None, receipt_timestamp=None, order_type=None):
    if symbol not in data:
        data[symbol] = {'min': price, 'max': price}
    else:
        if price > data[symbol]['max']:
            data[symbol]['max'] = price
        elif price < data[symbol]['min']:
            data[symbol]['min'] = price


def init(data):
    """
    called at start of each new interval. We just need to clear the
    internal state
    """
    data.clear()


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: CustomAggregate(Callback(callback), window=30, init=init, aggregator=custom_agg)}))

    f.run()


if __name__ == '__main__':
    main()

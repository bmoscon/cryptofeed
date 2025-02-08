'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import COINBASE, TRADES, L2_BOOK


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp, order_type):
    pass


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    pass


def main():
    config = {'log': {'filename': 'demo.log', 'level': 'INFO'}}
    f = FeedHandler(config=config)

    f.add_feed(COINBASE, subscription={L2_BOOK: ['BTC-USD', 'ETH-USD'], TRADES: ['ETH-USD']}, callbacks={TRADES: trade, L2_BOOK: book})

    f.run()


if __name__ == '__main__':
    import cProfile
    cProfile.run('main()', sort='cumulative')

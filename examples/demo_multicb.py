'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import TradeCallback
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    print("Timestamp: {} Feed: {} Pair: {} ID: {} Side: {} Amount: {} Price: {}".format(timestamp, feed, symbol, order_id, side, amount, price))


async def trade2(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    print("Trade2 Callback")


def main():
    f = FeedHandler()

    f.add_feed(Coinbase(subscription={TRADES: ['BTC-USD']}, callbacks={TRADES: [TradeCallback(trade), TradeCallback(trade2)]}))

    f.run()


if __name__ == '__main__':
    main()

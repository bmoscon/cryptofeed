'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback
from cryptofeed.defines import BID, ASK, L3_BOOK, TRADES
from cryptofeed.exchanges import Coinbase


async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print("Timestamp: {} Feed: {} Pair: {} ID: {} Side: {} Amount: {} Price: {}".format(timestamp, feed, pair, order_id, side, amount, price))


async def trade2(feed, pair, order_id, timestamp, side, amount, price):
    print("Trade2 Callback")


def main():
    f = FeedHandler()

    f.add_feed(Coinbase(config={TRADES: ['BTC-USD']}, callbacks={TRADES: [TradeCallback(trade), TradeCallback(trade2)]}))

    f.run()


if __name__ == '__main__':
    main()

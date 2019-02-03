'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import TradeCallback, BookCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import L3_BOOK, BID, ASK, TRADES



async def trade(feed, pair, order_id, timestamp, side, amount, price):
    print("Timestamp: {} Feed: {} Pair: {} ID: {} Side: {} Amount: {} Price: {}".format(timestamp, feed, pair, order_id, side, amount, price))


async def book(feed, pair, book, timestamp):
    print('Timestamp: {} Feed: {} Pair: {} Book Bid Size is {} Ask Size is {}'.format(timestamp, feed, pair, len(book[BID]), len(book[ASK])))


def main():
    f = FeedHandler()

    f.add_feed(Coinbase(config={TRADES: ['BTC-USD'], L3_BOOK: ['ETH-USD']}, callbacks={TRADES: TradeCallback(trade), L3_BOOK: BookCallback(book)}))

    f.run()


if __name__ == '__main__':
    main()

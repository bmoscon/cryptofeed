'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time

from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback
from cryptofeed.defines import BID, ASK, L2_BOOK
from cryptofeed.exchanges import Bitmex


counter = 0
avg = 0
START = time.time()
STATS = 1000


async def book(feed, symbol, book, timestamp):
    global counter
    global avg

    t = time.time()
    counter += 1
    bids = list(book[BID].keys())
    asks = list(book[ASK].keys())
    avg += (t - timestamp)

    try:
        assert (t - timestamp) < 2
        assert bids[-1] < asks[0]
    except Exception:
        print("FAILED")
        print("BID", bids[-1])
        print("ASKS", asks[0])
        print("DELTA", t - timestamp)
        print("COUNTER", counter)

    if counter % STATS == 0:
        print("Checked", counter, "updates")
        print("Runtime", t - START)
        print("Current spread", asks[0] - bids[-1])
        print("Average book update handle time", avg / counter)
        print("\n")


def main():
    f = FeedHandler()

    f.add_feed(Bitmex(symbols=['BTC-USD'], channels=[L2_BOOK], callbacks={L2_BOOK: BookCallback(book)}))
    f.run()


if __name__ == '__main__':
    main()

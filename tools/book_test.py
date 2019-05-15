'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import time

from cryptofeed.callback import BookCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Bitmex
from cryptofeed.defines import L3_BOOK, L2_BOOK, BID, ASK


counter = 0
avg = 0
START = time.time()
STATS = 1000


async def book(feed, pair, book, timestamp):
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
    except:
        print("FAILED")
        print("BID", bids[-1])
        print("ASKS", asks[0])
        print("DELTA", t - timestamp)
        print*("COUNTER", counter)
    
    if counter % STATS == 0:
        print("Checked", counter, "updates")
        print("Runtime", t - START)
        print("Current spread", asks[0] - bids[-1])
        print("Average book update handle time", avg / counter)
        print("\n")


def main():
    f = FeedHandler()

    f.add_feed(Bitmex(pairs=['XBTUSD'], channels=[L3_BOOK], callbacks={L3_BOOK: BookCallback(book)}))
    f.run()


if __name__ == '__main__':
    main()

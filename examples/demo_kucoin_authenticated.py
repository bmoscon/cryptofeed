'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com
Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import KUCOIN, L2_BOOK

from pprint import pprint
from time import time as timer

last_print = 0


async def book(**kwargs):
    global last_print
    now = timer()
    if now - last_print > 10 or last_print == 0:
        print("Book Update:")
        pprint(kwargs)
        last_print = now


def main():
    f = FeedHandler(config="config.yaml")
    f.add_feed(KUCOIN, subscription={L2_BOOK: ['BTC-USDT', 'ETH-USDT']}, callbacks={L2_BOOK: book})

    f.run()


if __name__ == '__main__':
    main()

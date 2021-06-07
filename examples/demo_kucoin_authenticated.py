'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import KUCOIN, L2_BOOK


async def book(**kwargs):
    print(f"Book Update: {kwargs}")


def main():
    f = FeedHandler(config="config.yaml")
    f.add_feed(KUCOIN, sandbox=True, subscription={L2_BOOK: ['BTC-USDT', 'ETH-USDT']}, callbacks={L2_BOOK: book})

    f.run()


if __name__ == '__main__':
    main()

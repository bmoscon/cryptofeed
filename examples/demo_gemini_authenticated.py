'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import GEMINI, ORDER_INFO


async def order(**kwargs):
    print(f"Order Update: {kwargs}")


def main():
    f = FeedHandler(config="config.yaml")
    f.add_feed(GEMINI, sandbox=True, subscription={ORDER_INFO: ['BTC-USD', 'ETH-USD']}, callbacks={ORDER_INFO: order})

    f.run()


if __name__ == '__main__':
    main()

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import OKEX, ORDER_INFO
from cryptofeed.callback import OrderInfoCallback


async def order(**kwargs):
    print(f"Order Update: {kwargs}")


def main():
    f = FeedHandler(config="config.yaml")
    f.add_feed(OKEX, channels=[ORDER_INFO], symbols=['BTC-USDT'], callbacks={ORDER_INFO: OrderInfoCallback(order)})
    f.run()


if __name__ == '__main__':
    main()

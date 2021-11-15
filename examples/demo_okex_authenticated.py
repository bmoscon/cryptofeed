'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.callback import OrderInfoCallback
from cryptofeed.defines import OKEX, ORDER_INFO


async def order(oi, receipt_timestamp):
    print(f"Order update received at {receipt_timestamp}: {oi}")


def main():

    path_to_config = 'config.yaml'
    f = FeedHandler(config=path_to_config)
    f.add_feed(OKEX,
               channels=[ORDER_INFO],
               symbols=["ETH-USDT-PERP", "BTC-USDT-PERP"],
               callbacks={ORDER_INFO: OrderInfoCallback(order)},
               timeout=-1)
    f.run()


if __name__ == "__main__":
    main()

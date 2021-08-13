#!/usr/bin/env python

from cryptofeed import FeedHandler
from cryptofeed.callback import OrderInfoCallback, UserFillsCallback
from cryptofeed.defines import BYBIT, ORDER_INFO, USER_FILLS


async def order(feed, symbol, data: dict, receipt_timestamp):
    print(f"{feed}: {symbol}: Order update: {data}")


async def fill(feed, symbol, data: dict, receipt_timestamp):
    print(f"{feed}: {symbol}: Fill update: {data}")


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt):
    print(f"Timestamp: {timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


def main():

    f = FeedHandler(config="config.yaml")
    f.add_feed(BYBIT,
               channels=[USER_FILLS, ORDER_INFO],
               symbols=["ETH-USD-21Z31", "EOS-USD-PERP", "SOL-USDT-PERP"],
               callbacks={USER_FILLS: UserFillsCallback(fill), ORDER_INFO: OrderInfoCallback(order)},
               timeout=-1)

    f.run()


if __name__ == '__main__':
    main()

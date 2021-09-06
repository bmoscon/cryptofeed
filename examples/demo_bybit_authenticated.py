#!/usr/bin/env python

from cryptofeed import FeedHandler
from cryptofeed.defines import BYBIT, ORDER_INFO, FILLS


async def order(feed, symbol, data: dict, receipt_timestamp):
    print(f"{feed}: {symbol}: Order update: {data}")


async def fill(feed, symbol, data: dict, receipt_timestamp):
    print(f"{feed}: {symbol}: Fill update: {data}")


async def trade(trade, receipt):
    print("Trade", trade)


def main():

    f = FeedHandler(config="config.yaml")
    f.add_feed(BYBIT,
               channels=[FILLS, ORDER_INFO],
               symbols=["ETH-USD-21Z31", "EOS-USD-PERP", "SOL-USDT-PERP"],
               callbacks={FILLS: fill, ORDER_INFO: order},
               timeout=-1)

    f.run()


if __name__ == '__main__':
    main()

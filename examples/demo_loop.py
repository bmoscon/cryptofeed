'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal

from cryptofeed import FeedHandler
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp, order_type):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


f = FeedHandler()


def stop():
    loop = asyncio.get_event_loop()
    loop.stop()


def add_new_feed():
    loop = asyncio.get_event_loop()
    f.add_feed_running(Coinbase(symbols=['ETH-USD'], channels=[TRADES], callbacks={TRADES: trade}), loop=loop)


def main():
    loop = asyncio.get_event_loop()
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[TRADES], callbacks={TRADES: trade}))
    f.run(start_loop=False)

    loop.call_later(2, add_new_feed)
    loop.call_later(15, stop)
    loop.run_forever()


if __name__ == '__main__':
    main()

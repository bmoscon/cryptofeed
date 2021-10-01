'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import ORDER_INFO, TRADES, FILLS
from cryptofeed.exchanges import FTX


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def trade(t, receipt_timestamp):
    print(t)


async def fill(data, receipt_timestamp):
    print(data)


async def order(data, receipt_timestamp):
    print(data)


def main():
    ftx = FTX(config='config.yaml', subaccount='subaccount')
    print(ftx.ticker_sync('ETH-USD'))
    print(ftx.orders_sync(symbol='USDT-USD'))
    f = FeedHandler(config="config.yaml")
    f.add_feed(FTX(config="config.yaml", subaccount='subaccount', symbols=['BTC-USD', 'BCH-USD', 'USDT-USD'], channels=[TRADES, FILLS, ORDER_INFO], callbacks={TRADES: trade, FILLS: fill, ORDER_INFO: order}))
    f.run()


if __name__ == '__main__':
    main()

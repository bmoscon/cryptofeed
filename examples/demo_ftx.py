'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal

from cryptofeed import FeedHandler
from cryptofeed.callback import TradeCallback
from cryptofeed.defines import TRADES, USER_FILLS
from cryptofeed.exchanges import FTX
from cryptofeed.rest import Rest


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"TRADE Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def fill(feed, symbol, order_id, trade_id, timestamp, side, amount, price, liquidity, receipt_timestamp):
    print(f'FILL Timestamp: {timestamp} Cryptofeed Receipt: {receipt_timestamp} Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}')


def main():
    ftx = Rest(config='config.yaml')['ftx']
    print(ftx.ticker('ETH-USD'))
    print(ftx.orders(symbol='USDT-USD'))
    f = FeedHandler(config="config.yaml")
    f.add_feed(FTX(config="config.yaml", symbols=['BTC-USD', 'BCH-USD', 'USDT-USD'], channels=[TRADES, USER_FILLS], callbacks={TRADES: TradeCallback(trade), USER_FILLS: fill}))
    f.run()


if __name__ == '__main__':
    main()

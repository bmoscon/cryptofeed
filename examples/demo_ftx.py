'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import datetime
from decimal import Decimal
import os
from pathlib import Path

from cryptofeed import FeedHandler
from cryptofeed.callback import BookCallback, TradeCallback
from cryptofeed.defines import BID, ASK, BUY, L2_BOOK, TICKER, TRADES, USER_FILLS
from cryptofeed.exchanges import FTX
from cryptofeed.rest.rest import Rest


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(feed, symbol, bid, ask, timestamp, receipt_timestamp):
    print(f'Timestamp: {get_time_from_timestamp(timestamp * 1000)} Cryptofeed Receipt: {get_time_from_timestamp(receipt_timestamp * 1000)} (+{receipt_timestamp * 1000 - timestamp * 1000}) Feed: {feed} Pair: {symbol} Bid: {bid} Ask: {ask}')


async def trade(feed, symbol, order_id, timestamp, side, amount, price, receipt_timestamp):
    assert isinstance(timestamp, float)
    assert isinstance(side, str)
    assert isinstance(amount, Decimal)
    assert isinstance(price, Decimal)
    print(f"Timestamp: {get_time_from_timestamp(timestamp * 1000)} Cryptofeed Receipt: {get_time_from_timestamp(receipt_timestamp * 1000)} (+{receipt_timestamp * 1000 - timestamp * 1000}) Feed: {feed} Pair: {symbol} ID: {order_id} Side: {side} Amount: {amount} Price: {price}")


async def book(feed, symbol, book, timestamp, receipt_timestamp):
    print(f'Timestamp: {get_time_from_timestamp(timestamp * 1000)} Cryptofeed Receipt: {get_time_from_timestamp(receipt_timestamp * 1000)} (+{receipt_timestamp * 1000 - timestamp * 1000}) Feed: {feed} Pair: {symbol} Book Bid Size is {len(book[BID])} Ask Size is {len(book[ASK])}')


async def fill(feed, symbol, order_id, trade_id, timestamp, side, amount, price, liquidity, receipt_timestamp):
    print(f"Timestamp: {get_time_from_timestamp(timestamp * 1000)} Cryptofeed Receipt: {get_time_from_timestamp(receipt_timestamp * 1000)} (+{receipt_timestamp * 1000 - timestamp * 1000}) Feed: {feed} Pair: {symbol} ID: {order_id} Trade ID: {trade_id} Side: {side} Amount: {amount} Price: {price} Liquidity: {liquidity}")


def get_time_from_timestamp(timestamp):
    s, ms = divmod(timestamp, 1000)
    return '%s.%03d' % (datetime.datetime.utcfromtimestamp(s).strftime('%H:%M:%S'), ms)


def main():
    path_to_config = os.path.join(Path.home(), 'config.yaml')

    ftx = Rest(config=path_to_config, subaccount='subaccount')['ftx']
    # print(ftx.config)
    print(ftx.ticker('ETH-USD'))
    print(ftx.orders(symbol='USDT-USD'))
    print(ftx.place_order(symbol='USDT-USD', side=BUY, amount=0.01, price=0.9995, post_only=True))
    print(ftx.orders(symbol='USDT-USD'))

    # callbacks={L2_BOOK: BookCallback(book), TICKER: ticker, TRADES: TradeCallback(trade), USER_FILLS: fill}
    # callbacks={USER_FILLS: fill}
    # f = FeedHandler()
    # f.add_feed(FTX(config=path_to_config, subaccount='subaccount', symbols=['ETH-USD', 'ETH-PERP','ETH-0625'], channels=[TRADES, L2_BOOK, TICKER, USER_FILLS], callbacks=callbacks))
    # f.run()


if __name__ == '__main__':
    main()

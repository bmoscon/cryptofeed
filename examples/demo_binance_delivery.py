'''
Copyright (C) 2018-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from datetime import datetime
from decimal import Decimal

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import BinanceDelivery


info = BinanceDelivery.info()


async def abook(book, receipt_timestamp):
    print(f'BOOK lag: {receipt_timestamp - book.timestamp} Timestamp: {datetime.fromtimestamp(book.timestamp)} Receipt Timestamp: {datetime.fromtimestamp(receipt_timestamp)}')


async def ticker(t, receipt_timestamp):
    if t.timestamp is not None:
        assert isinstance(t.timestamp, float)
    assert isinstance(t.exchange, str)
    assert isinstance(t.bid, Decimal)
    assert isinstance(t.ask, Decimal)
    print(f'Ticker received at {receipt_timestamp}: {t}')


async def trades(t, receipt_timestamp):
    assert isinstance(t.timestamp, float)
    assert isinstance(t.side, str)
    assert isinstance(t.amount, Decimal)
    assert isinstance(t.price, Decimal)
    assert isinstance(t.exchange, str)
    print(f"Trade received at {receipt_timestamp}: {t}")


def main():
    f = FeedHandler()
    f.add_feed(BinanceDelivery(max_depth=3, symbols=[info['symbols'][-1]],
                               channels=[L2_BOOK, TRADES, TICKER],
                               callbacks={L2_BOOK: abook, TRADES: trades, TICKER: ticker}))
    f.run()


if __name__ == '__main__':
    main()

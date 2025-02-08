'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from cryptofeed import FeedHandler
from cryptofeed.defines import CANDLES, BID, ASK, L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import BinanceTR
from cryptofeed.symbols import Symbol


async def ticker(t, receipt_timestamp):
    if t.timestamp is not None:
        assert isinstance(t.timestamp, float)
    assert isinstance(t.exchange, str)
    assert isinstance(t.bid, Decimal)
    assert isinstance(t.ask, Decimal)
    print(f'Ticker received at {receipt_timestamp}: {t}')


async def trade(t, receipt_timestamp):
    assert isinstance(t.timestamp, float)
    assert isinstance(t.side, str)
    assert isinstance(t.amount, Decimal)
    assert isinstance(t.price, Decimal)
    assert isinstance(t.exchange, str)
    print(f"Trade received at {receipt_timestamp}: {t}")


async def book(book, receipt_timestamp):
    print(f'Book received at {receipt_timestamp} for {book.exchange} - {book.symbol}, with {len(book.book)} entries. Top of book prices: {book.book.asks.index(0)[0]} - {book.book.bids.index(0)[0]}')
    if book.delta:
        print(f"Delta from last book contains {len(book.delta[BID]) + len(book.delta[ASK])} entries.")
    if book.sequence_number:
        assert isinstance(book.sequence_number, int)


async def candle_callback(c, receipt_timestamp):
    print(f"Candle received at {receipt_timestamp}: {c}")


def main():
    config = {'log': {'filename': 'demo.log', 'level': 'DEBUG', 'disabled': False}}
    f = FeedHandler(config=config)

    f.add_feed(BinanceTR(symbols=[Symbol('BTC', 'TRY')], channels=[CANDLES, L2_BOOK, TRADES, TICKER], callbacks={CANDLES: candle_callback, TICKER: ticker, L2_BOOK: book, TRADES: trade}))
    f.run()


if __name__ == '__main__':
    main()

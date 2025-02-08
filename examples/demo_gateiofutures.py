'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
from cryptofeed import FeedHandler
from cryptofeed.defines import CANDLES, BID, ASK, L2_BOOK, TICKER, TRADES, FUNDING, OPEN_INTEREST, INDEX
from cryptofeed.exchanges import GateioFutures


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


async def funding(f, receipt_timestamp):
    print(f"Funding update received at {receipt_timestamp}: {f}")


async def oi(update, receipt_timestamp):
    print(f"Open Interest update received at {receipt_timestamp}: {update}")


async def index(i, receipt_timestamp):
    print(f"Index received at {receipt_timestamp}: {i}")


async def candle_callback(c, receipt_timestamp):
    print(f"Candle received at {receipt_timestamp}: {c}")


def main():
    config = {'log': {'filename': 'demo.log', 'level': 'DEBUG', 'disabled': False}}
    f = FeedHandler(config=config)

    f.add_feed(GateioFutures(symbols=["BTC-USDT-PERP"], channels=[CANDLES, L2_BOOK, TRADES, TICKER], callbacks={CANDLES: candle_callback, TICKER: ticker, L2_BOOK: book, TRADES: trade}))
    f.add_feed(GateioFutures(symbols=["ETH-USDT-PERP"], channels=[FUNDING, INDEX, OPEN_INTEREST], callbacks={FUNDING: funding, INDEX: index, OPEN_INTEREST: oi}))
    f.run()


if __name__ == '__main__':
    main()

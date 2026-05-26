'''
LMEX Spot + Futures - cryptofeed demo
======================================
Run:
    python examples/demo_lmex.py

Prints real-time trades and L2 book updates for BTC-USD (spot)
and BTC-USD-PERP (futures), plus funding rates on a 60-second
poll cycle.

No API credentials required for public channels.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, TRADES, FUNDING
from cryptofeed.exchanges import LMEX, LMEXFutures


async def trade_callback(trade, receipt_timestamp):
    print(f'[TRADE]  {trade.exchange:<15} {trade.symbol:<14} {trade.side:<4} {trade.amount} @ {trade.price}  (ts={trade.timestamp:.3f})')


async def book_callback(book, receipt_timestamp):
    best_bid = max(book.book.bids.keys()) if book.book.bids else None
    best_ask = min(book.book.asks.keys()) if book.book.asks else None
    print(f'[BOOK]   {book.exchange:<15} {book.symbol:<14} bid={best_bid}  ask={best_ask}')


async def funding_callback(funding, receipt_timestamp):
    print(f'[FUNDING]{funding.exchange:<15} {funding.symbol:<14} rate={funding.rate}  mark={funding.mark_price}')


def main():
    fh = FeedHandler()

    fh.add_feed(LMEX(symbols=['BTC-USD'], channels=[TRADES, L2_BOOK], callbacks={TRADES: trade_callback, L2_BOOK: book_callback}))

    fh.add_feed(LMEXFutures(symbols=['BTC-USD-PERP'], channels=[TRADES, L2_BOOK, FUNDING], funding_interval=60, callbacks={TRADES: trade_callback, L2_BOOK: book_callback, FUNDING: funding_callback}))

    fh.run()


if __name__ == '__main__':
    main()

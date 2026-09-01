'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.exchanges import EXCHANGE_MAP, INDEPENDENT_RESERVE


BASE = 'BTC'
QUOTE_PREFERENCE = ('USD', 'USDT', 'USDC', 'EUR', 'GBP', 'JPY', 'KRW')
SYMBOL_CACHE_TTL = 3600


async def trade(t, receipt_timestamp):
    print(f'TRADE {t.exchange:<16} {t.symbol:<20} {t.side:<4} {t.amount} @ {t.price} (exchange ts {t.timestamp}, received {receipt_timestamp})')


async def book(b, receipt_timestamp):
    if not len(b.book.bids) or not len(b.book.asks):
        return

    bid, bid_size = b.book.bids.index(0)
    ask, ask_size = b.book.asks.index(0)
    print(f'BOOK  {b.exchange:<16} {b.symbol:<20} bid {bid_size} @ {bid} | ask {ask_size} @ {ask} ({len(b.book.bids)}x{len(b.book.asks)} levels, received {receipt_timestamp})')


def _rank(symbol: str) -> tuple:
    parts = symbol.split('-')
    quote_rank = QUOTE_PREFERENCE.index(parts[1]) if parts[1] in QUOTE_PREFERENCE else len(QUOTE_PREFERENCE)
    return (len(parts), quote_rank, 0 if parts[-1] == 'PERP' else 1, symbol)


def pick_symbol(symbols: list) -> str:
    pairs = [symbol for symbol in symbols if '-' in symbol]
    candidates = [symbol for symbol in pairs if symbol.split('-')[0] == BASE]
    return min(candidates or pairs, key=_rank)


async def main():
    fh = FeedHandler(on_feed_error='remove_feed')

    for name, exchange in EXCHANGE_MAP.items():
        # IR doesnt support L2 books
        if name == INDEPENDENT_RESERVE:
            continue

        try:
            await exchange.load_symbols(cache_ttl=SYMBOL_CACHE_TTL)
            symbol = pick_symbol(exchange.symbols())
        except Exception as e:
            print(f'{name}: skipping, unable to load symbols ({e})')
            continue

        print(f'{name}: subscribing to {symbol} - {TRADES} and {L2_BOOK}')
        fh.add_feed(name, symbols=[symbol], channels=[TRADES, L2_BOOK], callbacks={TRADES: trade, L2_BOOK: book})

    await fh.run_async()


if __name__ == '__main__':
    asyncio.run(main())

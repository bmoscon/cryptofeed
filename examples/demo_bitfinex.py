'''
Copyright (C) 2021-2021  Cryptofeed contributors

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from functools import partial

from cryptofeed import FeedHandler
from cryptofeed.defines import BOOK_DELTA, FUNDING, BITFINEX, L2_BOOK, L3_BOOK, TICKER, TRADES


async def print_all(*args, **kwargs):
    print(args, kwargs)


def main():

    config = {'log': {'filename': 'demo_bitfinex.log', 'level': 'DEBUG'}}
    f = FeedHandler(config=config)

    callbacks = {
        FUNDING: partial(print_all, FUNDING),
        TRADES: partial(print_all, TRADES),
        TICKER: partial(print_all, TICKER),
        L2_BOOK: partial(print_all, L2_BOOK),
        L3_BOOK: partial(print_all, L3_BOOK),
        BOOK_DELTA: partial(print_all, BOOK_DELTA),
    }

    # OK
    f.add_feed(BITFINEX, symbols=['BTC-USD'], channels=[TRADES], callbacks=callbacks)
    f.add_feed(BITFINEX, symbols=['BTC-USD'], channels=[TICKER], callbacks=callbacks)
    f.add_feed(BITFINEX, symbols=['BTC-USD'], channels=[L2_BOOK], callbacks=callbacks)
    f.add_feed(BITFINEX, symbols=['BTC-USD'], channels=[L3_BOOK], callbacks=callbacks)

    # OK: TRADES FUNDING
    f.add_feed(BITFINEX, symbols=['BTC'], channels=[FUNDING], callbacks=callbacks)

    # Bad: following line subscribes to TRADES /!\
    f.add_feed(BITFINEX, symbols=['BTC-USD'], channels=[FUNDING], callbacks=callbacks)

    # Bad: following line subscribes to FUNDING /!\
    f.add_feed(BITFINEX, symbols=['BTC'], channels=[TRADES], callbacks=callbacks)

    # Warning: TICKER FUNDING not yet implemented -> do nothing
    f.add_feed(BITFINEX, symbols=['BTC'], channels=[TICKER], callbacks=callbacks)

    f.run()


if __name__ == '__main__':
    main()

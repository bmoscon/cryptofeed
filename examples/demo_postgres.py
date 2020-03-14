'''
Copyright (C) 2018-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.postgres import TradePostgres, TickerPostgres, BookPostgres, BookDeltaPostgres
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase

from cryptofeed.defines import TRADES, L2_BOOK, BOOK_DELTA, TICKER


postgres_cfg = {'host': '127.0.0.1', 'user': 'postgres', 'db': 'postgres', 'pw': 'password123'}


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(channels=[L2_BOOK, TRADES, TICKER], pairs=['BTC-USD'], callbacks={L2_BOOK: BookPostgres(**postgres_cfg), BOOK_DELTA: BookDeltaPostgres(**postgres_cfg), TICKER: TickerPostgres(**postgres_cfg), TRADES: TradePostgres(**postgres_cfg)}))
    f.run()


if __name__ == '__main__':
    main()

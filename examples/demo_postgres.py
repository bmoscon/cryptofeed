'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.postgres import BookDeltaPostgres, BookPostgres, DeribitTickerPostgres, DeribitTradePostgres
from cryptofeed.defines import BOOK_DELTA, L2_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Deribit


postgres_cfg = {'host': '127.0.0.1', 'user': 'postgres', 'db': 'fs', 'pw': None}


def main():
    f = FeedHandler()
    symbols = Deribit.get_instruments()
    print(len(symbols))
    # symbols = [symbol for symbol in symbols if symbol.endswith("-C") or symbol.endswith("-P")]
    print(len(symbols))
    f.add_feed(Deribit(channels=[TICKER, TRADES], symbols=symbols, callbacks={TICKER: DeribitTickerPostgres(**postgres_cfg), TRADES: DeribitTradePostgres(**postgres_cfg)}))
    f.run()


if __name__ == '__main__':

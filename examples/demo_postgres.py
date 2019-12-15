'''
Copyright (C) 2018-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.backends.postgres import TradePostgres, TickerPostgres
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase

from cryptofeed.defines import TRADES, FUNDING, TICKER


postgres_cfg = {'host': '127.0.0.1', 'user': 'postgres', 'db': 'postgres', 'pw': 'password123'}


def main():
    f = FeedHandler()
    f.add_feed(Coinbase(channels=[TRADES, TICKER], pairs=['BTC-USD'], callbacks={TICKER: TickerPostgres(**postgres_cfg), TRADES: TradePostgres(**postgres_cfg)}))
    f.run()


if __name__ == '__main__':
    main()

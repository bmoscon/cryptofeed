'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.postgres import CandlesPostgres, TickerPostgres, TradePostgres
from cryptofeed.defines import CANDLES, TICKER, TRADES
from cryptofeed.exchanges import Binance


postgres_cfg = {'host': '127.0.0.1', 'user': 'postgres', 'db': 'postgres', 'pw': 'password'}

"""
Sample SQL file to create tables for demo in postgres_tables.sql
"""


def main():
    f = FeedHandler()
    f.add_feed(Binance(channels=[CANDLES, TRADES, TICKER], symbols=['BTC-USDT'], callbacks={CANDLES: CandlesPostgres(**postgres_cfg), TICKER: TickerPostgres(**postgres_cfg), TRADES: TradePostgres(**postgres_cfg)}))
    f.run()


if __name__ == '__main__':
    main()

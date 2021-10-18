'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.postgres import CandlesPostgres, IndexPostgres, TickerPostgres, TradePostgres, OpenInterestPostgres, LiquidationsPostgres, FundingPostgres
from cryptofeed.defines import CANDLES, INDEX, TICKER, TRADES, OPEN_INTEREST, LIQUIDATIONS, FUNDING
from cryptofeed.exchanges import Bybit, Binance


postgres_cfg = {'host': '127.0.0.1', 'user': 'postgres', 'db': 'cryptofeed', 'pw': 'password'}

"""
Sample SQL file to create tables for demo in postgres_tables.sql
"""


def main():
    f = FeedHandler()
    f.add_feed(Bybit(channels=[CANDLES, TRADES, OPEN_INTEREST, INDEX, LIQUIDATIONS, FUNDING], symbols=['BTC-USD-PERP'], callbacks={FUNDING: FundingPostgres(**postgres_cfg), LIQUIDATIONS: LiquidationsPostgres(**postgres_cfg), CANDLES: CandlesPostgres(**postgres_cfg), OPEN_INTEREST: OpenInterestPostgres(**postgres_cfg), INDEX: IndexPostgres(**postgres_cfg), TRADES: TradePostgres(**postgres_cfg)}))
    f.add_feed(Binance(channels=[TICKER], symbols=['BTC-USDT'], callbacks={TICKER: TickerPostgres(**postgres_cfg)}))

    f.run()


if __name__ == '__main__':
    main()

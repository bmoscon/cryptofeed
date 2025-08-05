'''
Copyright (C) 2018-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.mysql import CandlesMySQL, IndexMySQL, TickerMySQL, TradeMySQL, OpenInterestMySQL, LiquidationsMySQL, FundingMySQL, BookMySQL
from cryptofeed.defines import CANDLES, INDEX, L2_BOOK, TICKER, TRADES, OPEN_INTEREST, LIQUIDATIONS, FUNDING
from cryptofeed.exchanges import Bybit, Binance


mysql_cfg = {'host': '127.0.0.1', 'port': 3306, 'user': 'mysql', 'db': 'cryptofeed', 'pw': 'password'}

"""
Sample SQL file to create tables for demo in mysql_tables.sql

If you prefer not to use the pre-defined tables, or you have a pre-existing database schema, Cryptofeed can map its data elements to your own table layout.
Create a dictionary which maps Cryptofeed's data names to your column names, and provide it to the custom_columns kwarg.
The dictionary can include any of the data names listed under each data type (class) in types.pyx.
Note: to insert book data in a JSONB column you need to include a 'data' key (not listed in types.pyx), e.g. {'data': 'json_book_update'}
You don't have to include all of the data elements and they can be listed in any order.
"""

column_mappings = {
    'symbol': 'pair',
    'open': 'o',
    'high': 'h',
    'low': 'l',
    'close': 'c',
    'volume': 'v',
    'timestamp': 'ts',
    'start': 'start',
    'stop': 'stop',
    'closed': 'closed',
}


def main():
    f = FeedHandler()
    f.add_feed(Bybit(channels=[CANDLES, TRADES, OPEN_INTEREST, INDEX, LIQUIDATIONS, FUNDING], symbols=['BTC-USD-PERP'], callbacks={FUNDING: FundingMySQL(**mysql_cfg), LIQUIDATIONS: LiquidationsMySQL(**mysql_cfg), CANDLES: CandlesMySQL(**mysql_cfg), OPEN_INTEREST: OpenInterestMySQL(**mysql_cfg), INDEX: IndexMySQL(**mysql_cfg), TRADES: TradeMySQL(**mysql_cfg)}))
    f.add_feed(Binance(channels=[TICKER], symbols=['LTC-USDT'], callbacks={TICKER: TickerMySQL(**mysql_cfg)}))
    f.add_feed(Binance(channels=[L2_BOOK], symbols=['LTC-USDT'], callbacks={L2_BOOK: BookMySQL(snapshot_interval=100, table='l2_book', **mysql_cfg)}))
    # The following feed shows custom_columns and uses the custom_candles table example from the bottom of mysql_tables.sql. Obviously you can swap this out for your own table layout, just update the dictionary above
    f.add_feed(Binance(channels=[CANDLES], symbols=['LTC-USDT'], callbacks={CANDLES: CandlesMySQL(**mysql_cfg, custom_columns=column_mappings, table='custom_candles')}))
    f.run()


if __name__ == '__main__':
    main()

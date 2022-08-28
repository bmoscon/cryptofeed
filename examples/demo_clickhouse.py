'''
Copyright (C) 2018-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.backends.clickhouse import CandlesClickHouse, IndexClickHouse, TickerClickHouse, TradeClickHouse, OpenInterestClickHouse, LiquidationsClickHouse, FundingClickHouse, BookClickHouse
from cryptofeed.defines import CANDLES, INDEX, L2_BOOK, TICKER, TRADES, OPEN_INTEREST, LIQUIDATIONS, FUNDING
from cryptofeed.exchanges import Bybit, Binance


ClickHouse_cfg = {'host': '127.0.0.1', 'db': 'cryptofeed'}

"""
Sample SQL file to create tables for demo in ClickHouse_tables.sql

If you prefer not to use the pre-defined tables, or you have a pre-existing database schema, Cryptofeed can map its data elements to your own table layout. Only thing that needs to be consistent is the "id" column, which is an auto-generated UUID. See the ClickhouseCallback class in cryptofeed/backends/clickhouse.py for more details.
Create a dictionary which maps Cryptofeed's data names to your column names, and provide it to the custom_columns kwarg.
The dictionary can include any of the data names listed under each data type (class) in types.pyx.
Note: to insert book data in a JSON column you need to include a 'data' key (not listed in types.pyx), e.g. {'data': 'json_book_update'}
Also note that JSON in Clickhouse is experimental, so by default we use the String data type for all JSON data.
You don't have to include all of the data elements and they can be listed in any order.
"""

column_mappings = {
    'symbol': 'pair',
    'exchange': 'exch',
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
    f.add_feed(Bybit(channels=[CANDLES, TRADES, OPEN_INTEREST, INDEX, LIQUIDATIONS, FUNDING], symbols=['BTC-USD-PERP'], callbacks={FUNDING: FundingClickHouse(**ClickHouse_cfg), LIQUIDATIONS: LiquidationsClickHouse(**ClickHouse_cfg), CANDLES: CandlesClickHouse(**ClickHouse_cfg), OPEN_INTEREST: OpenInterestClickHouse(**ClickHouse_cfg), INDEX: IndexClickHouse(**ClickHouse_cfg), TRADES: TradeClickHouse(**ClickHouse_cfg)}))
    f.add_feed(Binance(channels=[TICKER, TRADES], symbols=['BTC-USDT'], callbacks={TICKER: TickerClickHouse(**ClickHouse_cfg), TRADES: TradeClickHouse(**ClickHouse_cfg)}))
    f.add_feed(Binance(channels=[L2_BOOK], symbols=['LTC-USDT'], callbacks={L2_BOOK: BookClickHouse(snapshot_interval=100, table='l2_book', **ClickHouse_cfg)}))
    # The following feed shows custom_columns and uses the custom_candles table example from the bottom of ClickHouse_tables.sql. Obviously you can swap this out for your own table layout, just update the dictionary above
    f.add_feed(Binance(channels=[CANDLES], symbols=['FTM-USDT'], callbacks={CANDLES: CandlesClickHouse(**ClickHouse_cfg, custom_columns=column_mappings, table='custom_candles')}))
    f.run()


if __name__ == '__main__':
    main()

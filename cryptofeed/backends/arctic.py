'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import arctic
import pandas as pd

from cryptofeed.backends.backend import (BackendFundingCallback, BackendCandlesCallback, BackendOpenInterestCallback,
                                         BackendTickerCallback, BackendTradeCallback, BackendLiquidationsCallback,
                                         BackendMarketInfoCallback)
from cryptofeed.defines import CANDLES, FUNDING, OPEN_INTEREST, TICKER, TRADES, LIQUIDATIONS, MARKET_INFO


class ArcticCallback:
    def __init__(self, library, host='127.0.0.1', key=None, numeric_type=float, quota=0, ssl=False, **kwargs):
        """
        library: str
            arctic library. Will be created if does not exist.
        key: str
            setting key lets you override the symbol name.
            The defaults are related to the data
            being stored, i.e. trade, funding, etc
        quota: int
            absolute number of bytes that this library is limited to.
            The default of 0 means that the storage size is unlimited.
        kwargs:
            if library needs to be created you can specify the
            lib_type in the kwargs. Default is VersionStore, but you can
            set to chunkstore with lib_type=arctic.CHUNK_STORE
        """
        con = arctic.Arctic(host, ssl=ssl)
        if library not in con.list_libraries():
            lib_type = kwargs.get('lib_type', arctic.VERSION_STORE)
            con.initialize_library(library, lib_type=lib_type)
        con.set_quota(library, quota)
        self.lib = con[library]
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type

    async def write(self, feed, symbol, timestamp, receipt_timestamp, data):
        df = pd.DataFrame({key: [value] for key, value in data.items()})
        df['date'] = pd.to_datetime(df.timestamp, unit='s')
        df['receipt_timestamp'] = pd.to_datetime(df.receipt_timestamp, unit='s')
        df.set_index(['date'], inplace=True)
        df.drop(columns=['timestamp'], inplace=True)
        self.lib.append(self.key, df, upsert=True)


class TradeArctic(ArcticCallback, BackendTradeCallback):
    default_key = TRADES


class FundingArctic(ArcticCallback, BackendFundingCallback):
    default_key = FUNDING


class TickerArctic(ArcticCallback, BackendTickerCallback):
    default_key = TICKER


class OpenInterestArctic(ArcticCallback, BackendOpenInterestCallback):
    default_key = OPEN_INTEREST


class LiquidationsArctic(ArcticCallback, BackendLiquidationsCallback):
    default_key = LIQUIDATIONS


class MarketInfoArctic(ArcticCallback, BackendMarketInfoCallback):
    default_key = MARKET_INFO


class CandlesArctic(ArcticCallback, BackendCandlesCallback):
    default_key = CANDLES

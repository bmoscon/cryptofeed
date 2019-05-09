'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from decimal import Decimal
import time
from datetime import datetime as dt

import arctic
import pandas as pd

from cryptofeed.defines import TRADES, FUNDING


class ArcticCallback:
    def __init__(self, library, host='127.0.0.1', key=None, **kwargs):
        """
        library: str
            arctic library. Will be created if does not exist.
        key: str
            setting key lets you override the symbol name.
            The defaults are related to the data
            being stored, i.e. trade, funding, etc
        kwargs:
            if library needs to be created you can specify the
            lib_type in the kwargs. Default is VersionStore, but you can
            set to chunkstore with lib_type=arctic.CHUNK_STORE
        """
        con = arctic.Arctic(host)
        if library not in con.list_libraries():
            lib_type = kwargs.get('lib_type', arctic.VERSION_STORE)
            con.initialize_library(library, lib_type=lib_type)
        self.lib = con[library]
        self.key = key


class TradeArctic(ArcticCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = TRADES

    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        df = pd.DataFrame({'feed': [feed], 'pair': [pair], 'id': [order_id], 'date': [dt.utcfromtimestamp(timestamp)],
                           'side': [side], 'amount': [float(amount)], 'price': [float(price)]})
        df['date'] = pd.to_datetime(df.date)
        df.set_index(['date'], inplace=True)
        self.lib.append(self.key, df, upsert=True)


class FundingArctic(ArcticCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.key is None:
            self.key = FUNDING

    async def __call__(self, *, feed, pair, **kwargs):
        timestamp = kwargs.get('timestamp', None)

        if 'timestamp' in kwargs:
            del kwargs['timestamp']

        if timestamp is None:
            timestamp = time.time()

        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = [float(kwargs[key])]
            else:
                kwargs[key] = [kwargs[key]]

        kwargs['date'] = dt.utcfromtimestamp(timestamp)

        df = pd.DataFrame(kwargs)
        df['date'] = pd.to_datetime(df.date)
        df.set_index(['date'], inplace=True)
        self.lib.append(self.key, df, upsert=True)

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from typing import Dict

from cryptofeed.symbols import Symbols
from cryptofeed.defines import FUNDING, FUTURES_INDEX, LIQUIDATIONS, L2_BOOK, L3_BOOK, OPEN_INTEREST, TICKER, TRADES, CANDLES, USER_FILLS, ORDER_INFO, ACC_TRANSACTIONS, ACC_BALANCES
from cryptofeed.standards import feed_to_exchange
from cryptofeed.exceptions import UnsupportedDataFeed
from cryptofeed.connection import HTTPSync


LOG = logging.getLogger('feedhandler')


class Exchange:
    id = 'NotImplemented'
    symbol_endpoint = 'NotImplemented'
    http_sync = HTTPSync()
    _parse_symbol_data = 'NotImplemented'

    @classmethod
    def info(cls) -> Dict:
        """
        Return information about the Exchange for REST and Websocket data channels
        """
        symbols = cls.symbol_mapping()
        data = Symbols.get(cls.id)[1]
        data['symbols'] = list(symbols.keys())
        data['channels'] = []
        for channel in (FUNDING, FUTURES_INDEX, LIQUIDATIONS, L2_BOOK, L3_BOOK, OPEN_INTEREST, TICKER, TRADES, CANDLES, USER_FILLS, ORDER_INFO, ACC_TRANSACTIONS, ACC_BALANCES):
            try:
                feed_to_exchange(cls.id, channel, silent=True)
                data['channels'].append(channel)
            except UnsupportedDataFeed:
                pass

        return data

    @classmethod
    def symbols(cls, refresh=False) -> Dict:
        if refresh:
            cls.symbol_mapping(refresh=True)
        return cls.info()['symbols']

    @classmethod
    def symbol_mapping(cls, refresh=False) -> Dict:
        if Symbols.populated(cls.id) and not refresh:
            return Symbols.get(cls.id)[0]
        try:
            LOG.debug("%s: reading symbol information from %s", cls.id, cls.symbol_endpoint)
            if isinstance(cls.symbol_endpoint, list):
                data = []
                for ep in cls.symbol_endpoint:
                    data.append(cls.http_sync.read(ep, json=True, uuid=cls.id))
            elif isinstance(cls.symbol_endpoint, dict):
                data = []
                for input, output in cls.symbol_endpoint.items():
                    for d in cls.http_sync.read(input, json=True, uuid=cls.id):
                        data.append(cls.http_sync.read(f"{output}{d}", json=True, uuid=cls.id))
            else:
                data = cls.http_sync.read(cls.symbol_endpoint, json=True, uuid=cls.id)

            syms, info = cls._parse_symbol_data(data)
            Symbols.set(cls.id, syms, info)
            return syms
        except Exception as e:
            LOG.error("%s: Failed to parse symbol information: %s", cls.id, str(e), exc_info=True)
            raise

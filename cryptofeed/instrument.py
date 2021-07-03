'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.exchanges import EXCHANGE_MAP
from cryptofeed.feed import Feed
from cryptofeed.defines import SWAP, SPOT, FUTURE, OPTION


class Instrument:
    def __init__(self, symbol, exchange):
        self.exchange = exchange
        self.symbol = symbol
        self.normalized_symbol = Feed.exchange_symbol_to_std_symbol(EXCHANGE_MAP[exchange].id, symbol)
    
    
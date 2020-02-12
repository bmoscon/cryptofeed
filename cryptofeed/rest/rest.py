'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.rest.bitmex import Bitmex
from cryptofeed.rest.bitfinex import Bitfinex
from cryptofeed.rest.coinbase import Coinbase
from cryptofeed.rest.poloniex import Poloniex
from cryptofeed.rest.gemini import Gemini
from cryptofeed.rest.kraken import Kraken
from cryptofeed.rest.deribit import Deribit
from cryptofeed.log import get_logger
from cryptofeed.standards import load_exchange_pair_mapping


LOG = get_logger('rest', 'rest.log')


class Rest:
    """
    The rest class is a common interface for accessing the individual exchanges

    r = Rest()
    r.bitmex.trades('XBTUSD', '2018-01-01', '2018-01-01')

    The Rest class optionally takes two parameters, config, and sandbox. In the config file
    the api key and secrets can be specified. sandbox enables sandbox mode, if supported by the exchange.
    """
    def __init__(self, config=None, sandbox=False):
        self.config = config
        self.lookup = {
            'bitmex': Bitmex(config),
            'bitfinex': Bitfinex(config),
            'coinbase': Coinbase(config, sandbox=sandbox),
            'poloniex': Poloniex(config),
            'gemini': Gemini(config, sandbox=sandbox),
            'kraken': Kraken(config),
            'deribit': Deribit(config)
        }

    def __getitem__(self, key):
        exch = self.lookup[key.lower()]
        if not exch.mapped:
            try:
                load_exchange_pair_mapping(exch.ID + 'REST')
            except KeyError:
                load_exchange_pair_mapping(exch.ID)
            exch.mapped = True
        return exch

    def __getattr__(self, attr):
        exch = self.lookup[attr.lower()]
        if not exch.mapped:
            try:
                load_exchange_pair_mapping(exch.ID + 'REST')
            except KeyError:
                load_exchange_pair_mapping(exch.ID)
            exch.mapped = True
        return exch

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.config import Config
from cryptofeed.log import get_logger
from cryptofeed.rest.binance_futures import BinanceFutures, BinanceDelivery
from cryptofeed.rest.bitfinex import Bitfinex
from cryptofeed.rest.bitmex import Bitmex
from cryptofeed.rest.coinbase import Coinbase
from cryptofeed.rest.deribit import Deribit
from cryptofeed.rest.ftx import FTX
from cryptofeed.rest.gemini import Gemini
from cryptofeed.rest.kraken import Kraken
from cryptofeed.rest.poloniex import Poloniex


LOG = logging.getLogger('rest')


class Rest:
    """
    The rest class is a common interface for accessing the individual exchanges

    r = Rest()
    r.bitmex.trades('BTC-USD', '2018-01-01', '2018-01-01')

    The Rest class optionally takes two exchange-related parameters, config, and sandbox.
    In the config file the api key and secrets can be specified. Sandbox enables sandbox
    mode, if supported by the exchange.
    """

    def __init__(self, config=None, sandbox=False, subaccount=None):
        config = Config(config=config)

        get_logger('rest', config.rest.log.filename, config.rest.log.level)

        self.lookup = {
            'bitmex': Bitmex(config=config.bitmex),
            'bitfinex': Bitfinex(config=config.bitfinex),
            'coinbase': Coinbase(config=config.coinbase, sandbox=sandbox),
            'poloniex': Poloniex(config=config.poloniex),
            'gemini': Gemini(config=config.gemini, sandbox=sandbox),
            'kraken': Kraken(config=config.kraken),
            'deribit': Deribit(config=config.deribit),
            'binance_futures': BinanceFutures(config=config.binance_futures),
            'binance_delivery': BinanceDelivery(config=config.binance_delivery),
            'ftx': FTX(config=config.ftx, subaccount=subaccount)
        }

    def __getitem__(self, key):
        return self.lookup[key.lower()]

    def __getattr__(self, attr):
        return self.lookup[attr.lower()]

import logging

from cryptofeed.rest.bitmex import Bitmex
from cryptofeed.rest.bitfinex import Bitfinex
from cryptofeed.rest.coinbase import Coinbase
from cryptofeed.rest.poloniex import Poloniex
from cryptofeed.rest.gemini import Gemini
from cryptofeed.rest.kraken import Kraken
from cryptofeed.log import get_logger


LOG = get_logger('rest', 'rest.log')


class Rest:
    def __init__(self, config=None, sandbox=False):
        self.config = config
        self.lookup = {
            'bitmex': Bitmex(config),
            'bitfinex': Bitfinex(config),
            'coinbase': Coinbase(config, sandbox=sandbox),
            'poloniex': Poloniex(config),
            'gemini': Gemini(config, sandbox=sandbox),
            'kraken': Kraken(config)
        }

    def __getattr__(self, attr):
        return self.lookup[attr.lower()]

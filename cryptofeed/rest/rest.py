from cryptofeed.rest.bitmex import Bitmex
from cryptofeed.rest.bitfinex import Bitfinex
from cryptofeed.rest.coinbase import Coinbase
from cryptofeed.rest.poloniex import Poloniex
from cryptofeed.rest.gemini import Gemini
from cryptofeed.rest.kraken import Kraken
from cryptofeed.log import get_logger
from cryptofeed.standards import load_exchange_pair_mapping


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

    def __getitem__(self, key):
        exch = self.lookup[key.lower()]
        if not exch.mapped:
            load_exchange_pair_mapping(exch.ID)
            exch.mapped = True
        return exch

    def __getattr__(self, attr):
        exch = self.lookup[attr.lower()]
        if not exch.mapped:
            load_exchange_pair_mapping(exch.ID)
            exch.mapped = True
        return exch

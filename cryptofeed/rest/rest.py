import logging

from cryptofeed.rest.bitmex import Bitmex
from cryptofeed.rest.bitfinex import Bitfinex
from cryptofeed.rest.coinbase import Coinbase
from cryptofeed.rest.poloniex import Poloniex
from cryptofeed.rest.gemini import Gemini


FORMAT = '%(asctime)-15s : %(levelname)s : %(message)s'
logging.basicConfig(level=logging.WARNING,
                    format=FORMAT,
                    handlers=[logging.FileHandler('rest.log'),
                              logging.StreamHandler()])
LOG = logging.getLogger('rest')


class Rest:
    def __init__(self, config=None, sandbox=False):
        self.config = config
        self.lookup = {
            'bitmex': Bitmex(config),
            'bitfinex': Bitfinex(config),
            'coinbase': Coinbase(config, sandbox=sandbox),
            'poloniex': Poloniex(config),
            'gemini': Gemini(config, sandbox=sandbox)
        }

    def __getattr__(self, attr):
        return self.lookup[attr.lower()]

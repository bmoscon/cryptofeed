import logging

from cryptofeed.rest.bitmex import Bitmex
from cryptofeed.rest.bitfinex import Bitfinex


FORMAT = '%(asctime)-15s : %(levelname)s : %(message)s'
logging.basicConfig(level=logging.WARNING,
                    format=FORMAT,
                    handlers=[logging.FileHandler('rest.log'),
                              logging.StreamHandler()])
LOG = logging.getLogger('rest')


class Rest:
    def __init__(self, config=None):
        self.config = config
        self.lookup = {
            'bitmex': Bitmex(config),
            'bitfinex': Bitfinex(config)
        }
    
    def __getattr__(self, attr):
        return self.lookup[attr.lower()]
    
    

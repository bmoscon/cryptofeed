from cryptofeed.rest.bitmex import Bitmex
from cryptofeed.rest.bitfinex import Bitfinex


class Rest:
    def __init__(self, config):
        self.config = config
        self.lookup = {
            'bitmex': Bitmex(config),
            'bitfinex': Bitfinex(config)
        }
    
    def __getattr__(self, attr):
        return self.lookup[attr.lower()]
    
    

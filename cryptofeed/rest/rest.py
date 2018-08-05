from cryptofeed.rest.bitmex import Bitmex

class Rest:
    def __init__(self, config):
        self.config = config
        self.lookup = {
            'bitmex': Bitmex(config)
        }
    
    def __getattribute__(self, attr):
        return self.lookup[attr]
    
    

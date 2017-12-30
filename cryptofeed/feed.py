
class Feed(object):
    def __init__(self, address):
        self.address = address
    
    async def _print(self, update):
        print(update)

    def message_handler(self, msg):
        raise NotImplementedError

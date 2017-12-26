
class Feed(object):
    def __init__(self, address):
        self.address = address

    def message_handler(self, msg):
        raise NotImplementedError

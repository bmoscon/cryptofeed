'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
class Feed(object):
    def __init__(self, address):
        self.address = address

    def message_handler(self, msg):
        raise NotImplementedError

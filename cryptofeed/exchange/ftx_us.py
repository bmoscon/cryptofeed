'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.defines import FTX_US
from cryptofeed.exchange.ftx import FTX


LOG = logging.getLogger('feedhandler')


class FTXUS(FTX):
    id = FTX_US

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.address = 'wss://ftx.us/ws/'

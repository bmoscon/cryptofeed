'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.defines import HUOBI_US
from cryptofeed.huobi.huobi import Huobi


LOG = logging.getLogger('feedhandler')


class HuobiUS(Huobi):
    id = HUOBI_US

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, config=config, **kwargs)
        self.address = 'wss://api.huobi.pro/hbus/ws'

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.defines import HITBTC
from cryptofeed.exchanges import Bequant

LOG = logging.getLogger('feedhandler')


class HitBTC(Bequant):
    id = HITBTC
    symbol_endpoint = 'https://api.hitbtc.com/api/2/public/symbol'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.address = {
            'market': 'wss://api.hitbtc.com/api/2/ws/public',
            'trading': 'wss://api.hitbtc.com/api/2/ws/trading',
            'account': 'wss://api.hitbtc.com/api/2/ws/account',
        }

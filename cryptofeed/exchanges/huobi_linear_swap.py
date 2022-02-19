'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''

import logging

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import HUOBI_LINEAR_SWAP
from cryptofeed.exchanges.huobi_swap import HuobiSwap

LOG = logging.getLogger('feedhandler')


class HuobiLinearSwap(HuobiSwap):
    id = HUOBI_LINEAR_SWAP
    websocket_endpoints = [WebsocketEndpoint('wss://api.hbdm.com/linear-swap-ws')]
    rest_endpoints = [RestEndpoint('https://api.hbdm.com', routes=Routes('/linear-swap-api/v1/swap_contract_info', funding='/linear-swap-api/v1/swap_funding_rate?contract_code={}'))]
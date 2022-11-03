'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from typing import Dict, Tuple

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import INLOCK, L2_BOOK, TICKER
from cryptofeed.feed import Feed
from cryptofeed.symbols import Symbol
from cryptofeed.exchanges.mixins.inlock_rest import InlockRestMixin


LOG = logging.getLogger('feedhandler')


class Inlock(Feed, InlockRestMixin):
    id = INLOCK
    #websocket_endpoints = [WebsocketEndpoint('wss://api.inlock.io/inlock/api/v1.0')]
    rest_endpoints = [RestEndpoint('https://api.inlock.io/inlock/api/v1.0', routes=Routes("/public/tokenmarket/pairs"))]
    websocket_channels = {}
    request_limit = 10

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = {'instrument_type': {}}
        for entry in data:
            base = entry['base']
            quote = entry['target']
            s = Symbol(base, quote)
            ret[s.normalized] = entry['ticker_id']
            info['instrument_type'][s.normalized] = s.type
        return ret, info



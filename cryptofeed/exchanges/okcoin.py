'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import logging
from typing import Dict, Tuple


from cryptofeed.exchanges import OKX
from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import L2_BOOK, OKCOIN, TICKER, TRADES, SPOT, CANDLES
from cryptofeed.symbols import Symbol

LOG = logging.getLogger('feedhandler')


class OKCoin(OKX):
    id = OKCOIN
    websocket_endpoints = [WebsocketEndpoint('wss://real.okcoin.com:8443/ws/v5/public')]
    rest_endpoints = [RestEndpoint('https://www.okcoin.com', routes=Routes('/api/v5/public/instruments?instType=SPOT'))]
    websocket_channels = {
        L2_BOOK: 'books',
        TRADES: 'trades',
        TICKER: 'tickers',
        CANDLES: 'candle'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for e in data['data']:
            base = e['baseCcy']
            quote = e['quoteCcy']
            base, quote = e['instId'].split("-")
            s = Symbol(base, quote)
            ret[s.normalized] = e['instId']
            info['tick_size'][s.normalized] = e['tickSz']
            info['instrument_type'][s.normalized] = SPOT

        return ret, info

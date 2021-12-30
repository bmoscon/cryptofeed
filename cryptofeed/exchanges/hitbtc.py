'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint

from cryptofeed.defines import BALANCES, CANDLES, HITBTC, L2_BOOK, ORDER_INFO, TICKER, TRADES, TRANSACTIONS
from cryptofeed.exchanges import Bequant

LOG = logging.getLogger('feedhandler')


class HitBTC(Bequant):
    id = HITBTC
    websocket_endpoints = [
        WebsocketEndpoint('wss://api.hitbtc.com/api/2/ws/public', channel_filter=[L2_BOOK, TRADES, TICKER, CANDLES]),
        WebsocketEndpoint('wss://api.hitbtc.com/api/2/ws/trading', channel_filter=[ORDER_INFO]),
        WebsocketEndpoint('wss://api.hitbtc.com/api/2/ws/account', channel_filter=[BALANCES, TRANSACTIONS]),
    ]
    rest_endpoints = [RestEndpoint('https://api.hitbtc.com', routes=Routes('/api/2/public/symbol'))]

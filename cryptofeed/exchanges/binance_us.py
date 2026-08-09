'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.connection import RestEndpoint, WebsocketEndpoint, Routes
from cryptofeed.defines import BINANCE_US
from cryptofeed.exchanges.binance import Binance


LOG = logging.getLogger(__name__)


class BinanceUS(Binance):
    id = BINANCE_US
    websocket_endpoints = [WebsocketEndpoint('wss://stream.binance.us:9443')]
    rest_endpoints = [RestEndpoint('https://api.binance.us', routes=Routes('/api/v3/exchangeInfo', l2book='/api/v3/depth?symbol={}&limit={}'))]

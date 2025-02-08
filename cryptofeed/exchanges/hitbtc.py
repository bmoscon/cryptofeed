'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

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
    websocket_channels = {
        BALANCES: 'subscribeBalance',
        TRANSACTIONS: 'subscribeTransactions',
        ORDER_INFO: 'subscribeReports',
        L2_BOOK: 'subscribeOrderbook',
        TRADES: 'subscribeTrades',
        TICKER: 'subscribeTicker',
        CANDLES: 'subscribeCandles'
    }
    websocket_endpoints = [
        WebsocketEndpoint('wss://api.hitbtc.com/api/2/ws/public', channel_filter=(websocket_channels[L2_BOOK], websocket_channels[TRADES], websocket_channels[TICKER], websocket_channels[CANDLES])),
        WebsocketEndpoint('wss://api.hitbtc.com/api/2/ws/trading', channel_filter=(websocket_channels[ORDER_INFO],)),
        WebsocketEndpoint('wss://api.hitbtc.com/api/2/ws/account', channel_filter=(websocket_channels[BALANCES], websocket_channels[TRANSACTIONS])),
    ]
    rest_endpoints = [RestEndpoint('https://api.hitbtc.com', routes=Routes('/api/2/public/symbol'))]

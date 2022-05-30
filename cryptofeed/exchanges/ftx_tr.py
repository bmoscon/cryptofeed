"""
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
"""
import logging

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import FTX_TR, L2_BOOK, ORDER_INFO, TICKER, TRADES, FILLS
from cryptofeed.exchanges.ftx import FTX
from cryptofeed.exchanges.mixins.ftx_rest_tr import FTXTRRestMixin


LOG = logging.getLogger("feedhandler")


class FTXTR(FTX, FTXTRRestMixin):
    id = FTX_TR
    websocket_endpoints = [WebsocketEndpoint("wss://ftxtr.com/ws/", options={"compression": None})]
    rest_endpoints = [RestEndpoint("https://ftxtr.com", routes=Routes("/api/markets"))]

    websocket_channels = {
        L2_BOOK: "orderbook",
        TRADES: "trades",
        TICKER: "ticker",
        ORDER_INFO: "orders",
        FILLS: "fills",
    }

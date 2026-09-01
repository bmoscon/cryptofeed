'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging

from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint

from cryptofeed.defines import BINANCE_DELIVERY, FUNDING, LIQUIDATIONS, OPEN_INTEREST
from cryptofeed.exchanges.binance import BinanceBase


LOG = logging.getLogger(__name__)


class BinanceDelivery(BinanceBase):
    id = BINANCE_DELIVERY

    # https://binance-docs.github.io/apidocs/delivery/en/#testnet
    websocket_endpoints = [WebsocketEndpoint('wss://dstream.binance.com', options={'compression': None}, sandbox='wss://dstream.binancefuture.com')]
    rest_endpoints = [RestEndpoint('https://dapi.binance.com', routes=Routes('/dapi/v1/exchangeInfo', l2book='/dapi/v1/depth?symbol={}&limit={}', open_interest='/dapi/v1/openInterest?symbol={}'), sandbox='https://testnet.binancefuture.com')]

    valid_depths = [5, 10, 20, 50, 100, 500, 1000]
    valid_depth_intervals = {'100ms', '250ms', '500ms'}
    websocket_channels = {
        **BinanceBase.websocket_channels,
        FUNDING: 'markPrice',
        OPEN_INTEREST: 'open_interest',
        LIQUIDATIONS: 'forceOrder',
    }

    def _check_update_id(self, pair: str, msg: dict) -> bool:
        if self._l2_book[pair].delta is None and msg['u'] < self.last_update_id[pair]:
            return True
        elif msg['U'] <= self.last_update_id[pair] <= msg['u']:
            self.last_update_id[pair] = msg['u']
            return False
        elif self.last_update_id[pair] == msg['pu']:
            self.last_update_id[pair] = msg['u']
            return False
        else:
            self._drop_book(pair)
            LOG.warning("%s: %s missing book update detected, resetting that book", self.id, pair)
            return True


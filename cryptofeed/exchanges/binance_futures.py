'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import logging
from typing import Tuple, Dict


from cryptofeed.connection import RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import BINANCE_FUTURES, FUNDING, LIQUIDATIONS, OPEN_INTEREST
from cryptofeed.exchanges.binance import BinanceBase, _chunk

LOG = logging.getLogger(__name__)


class BinanceFutures(BinanceBase):
    id = BINANCE_FUTURES
    websocket_endpoints = [WebsocketEndpoint('wss://fstream.binance.com', sandbox='wss://stream.binancefuture.com', options={'compression': None})]
    rest_endpoints = [RestEndpoint('https://fapi.binance.com', sandbox='https://testnet.binancefuture.com', routes=Routes('/fapi/v1/exchangeInfo', l2book='/fapi/v1/depth?symbol={}&limit={}', open_interest='/fapi/v1/openInterest?symbol={}'))]

    # https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams/Important-WebSocket-Change-Notice
    PUBLIC_STREAMS = ('bookTicker', 'depth')

    valid_depths = [5, 10, 20, 50, 100, 500, 1000]
    valid_depth_intervals = {'100ms', '250ms', '500ms'}
    websocket_channels = {
        **BinanceBase.websocket_channels,
        FUNDING: 'markPrice',
        OPEN_INTEREST: 'open_interest',
        LIQUIDATIONS: 'forceOrder',
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        base, info = super()._parse_symbol_data(data)
        add = {}
        for symbol, orig in base.items():
            if "_" in orig:
                continue
            premium_index = symbol.replace('PERP', 'PINDEX')
            if premium_index == symbol:
                continue
            add[premium_index] = f"p{orig}"
        base.update(add)
        return base, info

    @classmethod
    def _route(cls, stream_name: str) -> str:
        suffix = stream_name.split('@', 1)[1] if '@' in stream_name else stream_name
        return 'public' if suffix.startswith(cls.PUBLIC_STREAMS) else 'market'

    def _address(self):
        routed = {}
        for name in self._stream_names():
            routed.setdefault(self._route(name), []).append(name)

        addresses = []
        for route, names in routed.items():
            base = f'{self.address}/{route}/stream?streams='
            addresses.extend(base + '/'.join(chunk) for chunk in _chunk(names, self.per_connection_limit))
        return addresses[0] if len(addresses) == 1 else addresses

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


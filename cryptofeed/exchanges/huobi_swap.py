'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from cryptofeed.symbols import Symbol, str_to_symbol
import logging
import time
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection, RestEndpoint, Routes, WebsocketEndpoint
from cryptofeed.defines import HUOBI_SWAP, FUNDING, PERPETUAL
from cryptofeed.exchanges.huobi_dm import HuobiDM
from cryptofeed.types import Funding


LOG = logging.getLogger('feedhandler')


class HuobiSwap(HuobiDM):
    id = HUOBI_SWAP
    websocket_endpoints = [
        WebsocketEndpoint('wss://api.hbdm.com/swap-ws', instrument_filter=('QUOTE', ('USD',))),
        WebsocketEndpoint('wss://api.hbdm.com/linear-swap-ws', instrument_filter=('QUOTE', ('USDT',)))
    ]
    rest_endpoints = [
        RestEndpoint('https://api.hbdm.com', routes=Routes('/swap-api/v1/swap_contract_info', funding='/swap-api/v1/swap_funding_rate?contract_code={}'), instrument_filter=('QUOTE', ('USD',))),
        RestEndpoint('https://api.hbdm.com', routes=Routes('/linear-swap-api/v1/swap_contract_info', funding='/linear-swap-api/v1/swap_funding_rate?contract_code={}'), instrument_filter=('QUOTE', ('USDT',)))
    ]

    websocket_channels = {
        **HuobiDM.websocket_channels,
        FUNDING: 'funding'
    }

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)
        for d in data:
            for e in d['data']:
                base, quote = e['contract_code'].split("-")
                # Perpetual futures contract == perpetual swap
                s = Symbol(base, quote, type=PERPETUAL)
                ret[s.normalized] = e['contract_code']
                info['tick_size'][s.normalized] = e['price_tick']
                info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.funding_updates = {}

    async def _funding(self, pairs):
        """
        {
            "status": "ok",
            "data": {
                "estimated_rate": "0.000100000000000000",
                "funding_rate": "-0.000362360011416593",
                "contract_code": "BTC-USD",
                "symbol": "BTC",
                "fee_asset": "BTC",
                "funding_time": "1603872000000",
                "next_funding_time": "1603900800000"
            },
            "ts": 1603866304635
        }
        """
        while True:
            for pair in pairs:
                # use symbol to look up correct endpoint
                sym = str_to_symbol(self.exchange_symbol_to_std_symbol(pair))
                endpoint = None
                for ep in self.rest_endpoints:
                    if sym.quote in ep.instrument_filter[1]:
                        endpoint = self.rest_endpoints[0].route('funding').format(pair)

                data = await self.http_conn.read(endpoint)
                data = json.loads(data, parse_float=Decimal)
                received = time.time()
                update = (data['data']['funding_rate'], self.timestamp_normalize(int(data['data']['funding_time'])))
                if pair in self.funding_updates and self.funding_updates[pair] == update:
                    await asyncio.sleep(1)
                    continue
                self.funding_updates[pair] = update

                f = Funding(
                    self.id,
                    self.exchange_symbol_to_std_symbol(pair),
                    None,
                    Decimal(data['data']['funding_rate']),
                    self.timestamp_normalize(int(data['data']['next_funding_time'])) if data['data']['next_funding_time'] else None,
                    self.timestamp_normalize(int(data['data']['funding_time'])),
                    predicted_rate=Decimal(data['data']['estimated_rate']) if data['data']['estimated_rate'] is not None else None,
                    raw=data
                )
                await self.callback(FUNDING, f, received)
                await asyncio.sleep(0.1)

    async def subscribe(self, conn: AsyncConnection):
        if FUNDING in self.subscription:
            loop = asyncio.get_event_loop()
            loop.create_task(self._funding(self.subscription[FUNDING]))

        await super().subscribe(conn)

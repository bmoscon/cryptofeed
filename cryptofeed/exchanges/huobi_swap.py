'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from cryptofeed.symbols import Symbol
import logging
import time
from decimal import Decimal
from typing import Dict, Tuple

from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import HUOBI_SWAP, FUNDING, PERPETUAL
from cryptofeed.exchanges.huobi_dm import HuobiDM


LOG = logging.getLogger('feedhandler')


class HuobiSwap(HuobiDM):
    id = HUOBI_SWAP
    symbol_endpoint = 'https://api.hbdm.com/swap-api/v1/swap_contract_info'

    @classmethod
    def _parse_symbol_data(cls, data: dict) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for e in data['data']:
            base, quote = e['contract_code'].split("-")
            # Perpetual futures contract == perpetual swap
            s = Symbol(base, quote, type=PERPETUAL)
            ret[s.normalized] = e['contract_code']
            info['tick_size'][e['contract_code']] = e['price_tick']
            info['instrument_type'][s.normalized] = s.type

        return ret, info

    def __init__(self, **kwargs):
        self.websocket_channels[FUNDING] = 'funding'
        super().__init__(**kwargs)
        self.address = 'wss://api.hbdm.com/swap-ws'
        self.funding_updates = {}

    async def _funding(self, pairs):
        while True:
            for pair in pairs:
                data = await self.http_conn.read(f'https://api.hbdm.com/swap-api/v1/swap_funding_rate?contract_code={pair}')
                data = json.loads(data, parse_float=Decimal)
                received = time.time()
                update = (data['data']['funding_rate'], self.timestamp_normalize(int(data['data']['next_funding_time'])))
                if pair in self.funding_updates and self.funding_updates[pair] == update:
                    await asyncio.sleep(1)
                    continue
                self.funding_updates[pair] = update
                await self.callback(FUNDING,
                                    feed=self.id,
                                    symbol=pair,
                                    timestamp=self.timestamp_normalize(data['ts']),
                                    receipt_timestamp=received,
                                    rate=Decimal(update[0]),
                                    next_funding_time=update[1]
                                    )

                await asyncio.sleep(0.1)

    async def subscribe(self, conn: AsyncConnection):
        if FUNDING in self.subscription:
            loop = asyncio.get_event_loop()
            loop.create_task(self._funding(self.subscription[FUNDING]))

        await super().subscribe(conn)

import asyncio
from collections import defaultdict
import logging
import time
from decimal import Decimal
from typing import Dict, Tuple

import aiohttp
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import HUOBI_SWAP, FUNDING
from cryptofeed.exchange.huobi_dm import HuobiDM
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize


LOG = logging.getLogger('feedhandler')


class HuobiSwap(HuobiDM):
    id = HUOBI_SWAP
    symbol_endpoint = 'https://api.hbdm.com/swap-api/v1/swap_contract_info'

    @classmethod
    def _parse_symbol_data(cls, data: dict, symbol_separator: str) -> Tuple[Dict, Dict]:
        symbols = {}
        info = defaultdict(dict)

        for e in data['data']:
            symbols[e['contract_code']] = e['contract_code']
            info['tick_size'][e['contract_code']] = e['price_tick']
        return symbols, info

    def __init__(self, **kwargs):
        Feed.__init__(self, 'wss://api.hbdm.com/swap-ws', **kwargs)
        self.funding_updates = {}

    async def _funding(self, pairs):
        async with aiohttp.ClientSession() as session:
            while True:
                for pair in pairs:
                    async with session.get(f'https://api.hbdm.com/swap-api/v1/swap_funding_rate?contract_code={pair}') as response:
                        data = await response.text()
                        data = json.loads(data, parse_float=Decimal)

                        received = time.time()
                        update = (data['data']['funding_rate'], timestamp_normalize(self.id, int(data['data']['next_funding_time'])))
                        if pair in self.funding_updates and self.funding_updates[pair] == update:
                            await asyncio.sleep(1)
                            continue
                        self.funding_updates[pair] = update
                        await self.callback(FUNDING,
                                            feed=self.id,
                                            symbol=pair,
                                            timestamp=timestamp_normalize(self.id, data['ts']),
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

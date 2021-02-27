'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import logging
import time

import aiohttp
from yapic import json

from cryptofeed.connection import AsyncConnection
from cryptofeed.defines import OKEX, LIQUIDATIONS, BUY, SELL
from cryptofeed.exchange.okcoin import OKCoin


LOG = logging.getLogger("feedhandler")


class OKEx(OKCoin):
    """
    OKEx has the same api as OKCoin, just a different websocket endpoint
    """
    id = OKEX
    api = 'https://www.okex.com/api/'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.address = 'wss://real.okex.com:8443/ws/v3'

    async def _liquidations(self, pairs: list):
        last_update = {}
        async with aiohttp.ClientSession() as session:
            while True:
                for pair in pairs:
                    if 'SWAP' in pair:
                        instrument_type = 'swap'
                    else:
                        instrument_type = 'futures'

                    for status in (0, 1):
                        end_point = f"{self.api}{instrument_type}/v3/instruments/{pair}/liquidation?status={status}&limit=100"
                        async with session.get(end_point) as response:
                            data = await response.text()
                            data = json.loads(data, parse_float=Decimal)
                            timestamp = time.time()

                            if len(data) == 0 or (len(data) > 0 and last_update.get(pair) == data[0]):
                                continue
                            for entry in data:
                                if entry == last_update.get(pair):
                                    break

                                await self.callback(LIQUIDATIONS,
                                                    feed=self.id,
                                                    symbol=entry['instrument_id'],
                                                    side=BUY if entry['type'] == '3' else SELL,
                                                    leaves_qty=Decimal(entry['size']),
                                                    price=Decimal(entry['price']),
                                                    order_id=None,
                                                    status='filled' if status == 1 else 'unfilled',
                                                    timestamp=timestamp,
                                                    receipt_timestamp=timestamp
                                                    )
                            last_update[pair] = data[0]

                    await asyncio.sleep(0.1)
                await asyncio.sleep(60)

    async def subscribe(self, conn: AsyncConnection):
        if LIQUIDATIONS in self.subscription or LIQUIDATIONS in self.channels:
            pairs = self.subscription[LIQUIDATIONS] if LIQUIDATIONS in self.subscription else self.symbols
            asyncio.create_task(self._liquidations(pairs))  # TODO: use HTTPAsyncConn
        return await super().subscribe(conn)

'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import time

import aiohttp
import requests
from yapic import json

from cryptofeed.defines import OKEX, LIQUIDATIONS, BUY, SELL
from cryptofeed.exchange.okcoin import OKCoin


class OKEx(OKCoin):
    """
    OKEx has the same api as OKCoin, just a different websocket endpoint
    """
    id = OKEX
    api = 'https://www.okex.com/api/'

    def __init__(self, pairs=None, channels=None, callbacks=None, **kwargs):
        super().__init__(pairs=pairs, channels=channels, callbacks=callbacks, **kwargs)
        self.address = 'wss://real.okex.com:8443/ws/v3'
        self.book_depth = 200

    @staticmethod
    def get_active_symbols_info():
        return requests.get(OKEx.api + 'futures/v3/instruments').json()

    @staticmethod
    def get_active_symbols():
        symbols = []
        for data in OKEx.get_active_symbols_info():
            symbols.append(data['instrument_id'])
        return symbols

    @staticmethod
    def get_active_option_contracts_info(underlying: str):
        return requests.get(OKEx.api + f'option/v3/instruments/{underlying}').json()

    @staticmethod
    def get_active_option_contracts(underlying: str):
        symbols = []
        for data in OKEx.get_active_option_contracts_info(underlying):
            symbols.append(data['instrument_id'])
        return symbols

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
                                                    pair=entry['instrument_id'],
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

    async def subscribe(self, websocket):
        if LIQUIDATIONS in self.config or LIQUIDATIONS in self.channels:
            pairs = self.config[LIQUIDATIONS] if LIQUIDATIONS in self.config else self.pairs
            asyncio.create_task(self._liquidations(pairs))
        await super().subscribe(websocket)

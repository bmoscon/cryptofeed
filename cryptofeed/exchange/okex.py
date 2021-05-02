'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from collections import defaultdict
from decimal import Decimal
import logging
import time
from typing import Dict, Tuple

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
    symbol_endpoint = ['https://www.okex.com/api/spot/v3/instruments', 'https://www.okex.com/api/swap/v3/instruments', 'https://www.okex.com/api/futures/v3/instruments', 'https://www.okex.com/api/option/v3/instruments/BTC-USD', 'https://www.okex.com/api/option/v3/instruments/ETH-USD', 'https://www.okex.com/api/option/v3/instruments/EOS-USD']

    @classmethod
    def _parse_symbol_data(cls, data: list, symbol_separator: str) -> Tuple[Dict, Dict]:
        ret = {}
        info = defaultdict(dict)

        for entry in data:
            for e in entry:
                ret[e['instrument_id'].replace("-", symbol_separator)] = e['instrument_id']
                info['tick_size'][e['instrument_id']] = e['tick_size']

        for symbol in ret:
            instrument_type = 'futures'
            dash_count = symbol.count(symbol_separator)
            if dash_count == 1:  # BTC-USDT
                instrument_type = 'spot'
            if dash_count == 4:  # BTC-USD-201225-35000-P
                instrument_type = 'option'
            if symbol[-4:] == "SWAP":  # BTC-USDT-SWAP
                instrument_type = 'swap'
            info['instrument_type'][symbol] = instrument_type

        return ret, info

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.address = 'wss://real.okex.com:8443/ws/v3'

    async def _liquidations(self, pairs: list):
        last_update = {}

        while True:
            for pair in pairs:
                if 'SWAP' in pair:
                    instrument_type = 'swap'
                else:
                    instrument_type = 'futures'

                for status in (0, 1):
                    end_point = f"{self.api}{instrument_type}/v3/instruments/{pair}/liquidation?status={status}&limit=100"
                    data = await self.http_conn.read(end_point)
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
        if LIQUIDATIONS in self.subscription:
            asyncio.create_task(self._liquidations(self.subscription[LIQUIDATIONS]))
        return await super().subscribe(conn)

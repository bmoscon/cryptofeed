import logging
import asyncio
import time
from decimal import Decimal

import aiohttp
from yapic import json

from cryptofeed.defines import HUOBI_SWAP, FUNDING
from cryptofeed.exchange.huobi_dm import HuobiDM
from cryptofeed.feed import Feed
from cryptofeed.standards import timestamp_normalize


LOG = logging.getLogger('feedhandler')


class HuobiSwap(HuobiDM):
    id = HUOBI_SWAP

    def __init__(self, pairs=None, channels=None, callbacks=None, config=None, **kwargs):
        Feed.__init__(self, 'wss://api.hbdm.com/swap-ws', pairs=pairs, channels=channels, callbacks=callbacks, config=config, **kwargs)
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
                                            pair=pair,
                                            timestamp=timestamp_normalize(self.id, data['ts']),
                                            receipt_timestamp=received,
                                            rate=Decimal(update[0]),
                                            next_funding_time=update[1]
                                            )

                        await asyncio.sleep(0.1)

    async def subscribe(self, websocket):
        chans = list(self.channels)
        cfg = dict(self.config)
        if FUNDING in self.channels or FUNDING in self.config:
            loop = asyncio.get_event_loop()
            loop.create_task(self._funding(self.pairs if FUNDING in self.channels else self.config[FUNDING]))
            self.channels.remove(FUNDING) if FUNDING in self.channels else self.config.pop(FUNDING)

        await super().subscribe(websocket)
        self.channels = chans
        self.config = cfg

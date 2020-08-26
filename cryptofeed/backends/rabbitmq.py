'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import aio_pika
from yapic import json

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback, BackendLiquidationsCallback)


class RabbitCallback:
    def __init__(self, host='localhost', numeric_type=float, **kwargs):
        self.conn = None
        self.host = host
        self.numeric_type = numeric_type

    async def connect(self):
        if not self.conn:
            connection = await aio_pika.connect_robust(f"amqp://{self.host}/", loop=asyncio.get_running_loop())
            self.conn = await connection.channel()
            await self.conn.declare_queue('cryptofeed', auto_delete=False)

    async def write(self, feed: str, pair: str, timestamp: float, receipt_timestamp: float, data: dict):
        await self.connect()
        data['feed'] = feed
        data['pair'] = pair
        await self.conn.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(data).encode()
            ),
            routing_key='cryptofeed'
        )


class TradeRabbit(RabbitCallback, BackendTradeCallback):
    pass


class FundingRabbit(RabbitCallback, BackendFundingCallback):
    pass


class BookRabbit(RabbitCallback, BackendBookCallback):
    pass


class BookDeltaRabbit(RabbitCallback, BackendBookDeltaCallback):
    pass


class TickerRabbit(RabbitCallback, BackendTickerCallback):
    pass


class OpenInterestRabbit(RabbitCallback, BackendOpenInterestCallback):
    pass


class LiquidationsRabbit(RabbitCallback, BackendLiquidationsCallback):
    pass

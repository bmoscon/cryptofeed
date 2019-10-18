'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import json
import asyncio

import aio_pika

from cryptofeed.backends.backend import BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback, BackendTickerCallback, BackendTradeCallback


class RabbitCallback:
    def __init__(self, host='localhost', key=None, numeric_type=float, **kwargs):
        self.conn = None
        self.host = host
        self.numeric_type = numeric_type
        self.key = key if key else self.default_key

    async def connect(self):
        if not self.conn:
            connection = await aio_pika.connect_robust(f"amqp://{self.host}/", loop=asyncio.get_running_loop())
            self.conn = await connection.channel()
            await self.conn.declare_queue('cryptofeed', auto_delete=False)

    async def write(self, feed: str, pair: str, timestamp: float, data: dict):
        await self.connect()
        await self.conn.default_exchange.publish(
            aio_pika.Message(
                body=f'{self.key} {json.dumps(data)}'.encode()
            ),
            routing_key='cryptofeed'
        )


class TradeRabbit(RabbitCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingRabbit(RabbitCallback, BackendFundingCallback):
    default_key = 'funding'


class BookRabbit(RabbitCallback, BackendBookCallback):
    default_key = 'book'


class BookDeltaRabbit(RabbitCallback, BackendBookDeltaCallback):
    default_key = 'book'


class TickerRabbit(RabbitCallback, BackendTickerCallback):
    default_key = 'ticker'

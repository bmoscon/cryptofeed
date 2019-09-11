from decimal import Decimal
import json
import asyncio

import aio_pika

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class RabbitCallback:
    def __init__(self, host='localhost', **kwargs):
        self.conn = None
        self.host = host

    async def connect(self):
        if not self.conn:
            connection = await aio_pika.connect_robust(f"amqp://{self.host}/", loop=asyncio.get_running_loop())
            self.conn = await connection.channel()
            await self.conn.declare_queue('cryptofeed', auto_delete=False)


class TradeRabbit(RabbitCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        await self.connect()
        trade = {'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                 'side': side, 'amount': float(amount), 'price': float(price)}

        await self.conn.default_exchange.publish(
            aio_pika.Message(
                body=f'trades {json.dumps(trade)}'.encode()
            ),
            routing_key='cryptofeed'
        )


class FundingRabbit(RabbitCallback):
    async def __call__(self, **kwargs):
        await self.connect()
        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = float(kwargs[key])

        await self.conn.default_exchange.publish(
            aio_pika.Message(
                body=f'funding {json.dumps(kwargs)}'.encode()
            ),
            routing_key='cryptofeed'
        )


class BookRabbit(RabbitCallback):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def __call__(self, *, feed, pair, book, timestamp):
        await self.connect()
        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_convert(book, data)
        upd = {'feed': feed, 'pair': pair, 'delta': False, 'data': data}

        await self.conn.default_exchange.publish(
            aio_pika.Message(
                body=f'book {json.dumps(upd)}'.encode()
            ),
            routing_key='cryptofeed'
        )

class BookDeltaRabbit(RabbitCallback):
    async def __call__(self, *, feed, pair, delta, timestamp):
        await self.connect()
        data = {'timestamp': timestamp, BID: {}, ASK: {}}
        book_delta_convert(delta, data)
        upd = {'feed': feed, 'pair': pair, 'delta': True, 'data': data}

        await self.conn.default_exchange.publish(
            aio_pika.Message(
                body=f'book {json.dumps(upd)}'.encode()
            ),
            routing_key='cryptofeed'
        )

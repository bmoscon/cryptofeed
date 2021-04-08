'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

import aio_pika
from yapic import json

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)


class RabbitCallback:
    def __init__(self, host='localhost', numeric_type=float, queue_name='cryptofeed', exchange_mode=False, exchange_name='amq.topic', exchange_type='topic', routing_key='cryptofeed', **kwargs):
        """
        Parameters
        ----------
        host: str
            amqp URI scheme ('/' is assumed default vhost if not defined)
        exchange_mode: bool
            Setting key for using exchange and routing key modes
            Defaults to False.
        exchange_name: str
            name of AMQP exchange
        exchange_type: str
            exchange type
            String values must be one of ‘fanout’, ‘direct’, ‘topic’, ‘headers’, ‘x-delayed-message’, ‘x-consistent-hash'
        routing_key: str
            definable amqp routing key
        """
        self.conn = None
        self.host = host
        self.numeric_type = numeric_type
        self.queue_name = queue_name
        self.exchange_mode = exchange_mode
        self.exchange_name = exchange_name
        self.exchange_type = exchange_type
        self.routing_key = routing_key

    async def connect(self):
        if not self.conn:
            if self.exchange_mode:
                connection = await aio_pika.connect_robust(f"amqp://{self.host}", loop=asyncio.get_running_loop())
                self.conn = await connection.channel()
                self.conn = await self.conn.declare_exchange(self.exchange_name, self.exchange_type, durable=True, auto_delete=False)
            else:
                connection = await aio_pika.connect_robust(f"amqp://{self.host}", loop=asyncio.get_running_loop())
                self.conn = await connection.channel()
                await self.conn.declare_queue(self.queue_name, auto_delete=False)

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        await self.connect()
        data['feed'] = feed
        data['symbol'] = symbol

        if self.exchange_mode:
            await self.conn.publish(
                aio_pika.Message(
                    body=json.dumps(data).encode()
                ),
                routing_key=self.routing_key
            )
        else:
            await self.conn.default_exchange.publish(
                aio_pika.Message(
                    body=json.dumps(data).encode()
                ),
                routing_key=self.routing_key
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


class MarketInfoRabbit(RabbitCallback, BackendMarketInfoCallback):
    pass


class TransactionsRabbit(RabbitCallback, BackendTransactionsCallback):
    pass


class CandlesRabbit(RabbitCallback, BackendCandlesCallback):
    pass

'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import json

from aiokafka import AIOKafkaProducer


class KafkaCallback:
    def __init__(self, bootstrap='127.0.0.1', port=9092, topic=None, **kwargs):
        loop = asyncio.get_event_loop()
        self.producer = AIOKafkaProducer(acks=0,
                                         loop=loop,
                                         bootstrap_servers=f'{bootstrap}:{port}',
                                         client_id='cryptofeed')
        self.topic = topic

class TradeKafka(KafkaCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        if self.producer._sender.sender_task is None:
            await self.producer.start()

        data = json.dumps({'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                           'side': side, 'amount': str(amount), 'price': str(price)}).encode('utf8')
        topic = self.topic if self.topic else f"trades-{feed}-{pair}"
        await self.producer.send_and_wait(topic, data)

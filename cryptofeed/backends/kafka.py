'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
from decimal import Decimal
import json

from aiokafka import AIOKafkaProducer

from cryptofeed.defines import BID, ASK
from cryptofeed.backends._util import book_convert, book_delta_convert


class KafkaCallback:
    def __init__(self, bootstrap='127.0.0.1', port=9092, key=None, **kwargs):
        loop = asyncio.get_event_loop()
        self.producer = AIOKafkaProducer(acks=0,
                                         loop=loop,
                                         bootstrap_servers=f'{bootstrap}:{port}',
                                         client_id='cryptofeed')
        self.key = key

    async def _connect(self):
        if self.producer._sender.sender_task is None:
            await self.producer.start()


class TradeKafka(KafkaCallback):
    async def __call__(self, *, feed: str, pair: str, side: str, amount: Decimal, price: Decimal, order_id=None, timestamp=None):
        await self._connect()

        data = json.dumps({'feed': feed, 'pair': pair, 'id': order_id, 'timestamp': timestamp,
                           'side': side, 'amount': str(amount), 'price': str(price)}).encode('utf8')
        topic =  f"{self.key}-{feed}-{pair}" if self.key else f"trades-{feed}-{pair}"
        await self.producer.send_and_wait(topic, data)


class FundingKafka(KafkaCallback):
    async def __call__(self, *, feed, pair, **kwargs):
        await self._connect()

        for key in kwargs:
            if isinstance(kwargs[key], Decimal):
                kwargs[key] = str(kwargs[key])

        data = json.dumps(kwargs).encode('utf8')
        topic =  f"{self.key}-{feed}-{pair}" if self.key else f"funding-{feed}-{pair}"
        await self.producer.send_and_wait(topic, data)


class BookKafka(KafkaCallback):
    async def __call__(self, *, feed, pair, book, timestamp):
        await self._connect()

        data = {'timestamp': timestamp, 'delta': False, BID: {}, ASK: {}}
        book_convert(book, data)

        data = json.dumps(data).encode('utf8')
        topic =  f"{self.key}-{feed}-{pair}" if self.key else f"book-{feed}-{pair}"
        await self.producer.send_and_wait(topic, data)


class BookDeltaKafka(KafkaCallback):
    async def __call__(self, *, feed, pair, delta, timestamp):
        await self._connect()

        data = {'timestamp': timestamp, 'delta': True, BID: {}, ASK: {}}
        book_delta_convert(delta, data)

        data = json.dumps(data).encode('utf8')
        topic =  f"{self.key}-{feed}-{pair}" if self.key else f"book-{feed}-{pair}"
        await self.producer.send_and_wait(topic, data)


class TickerKafka(KafkaCallback):
    async def __call__(self, *, feed: str, pair: str, bid: Decimal, ask: Decimal, timestamp: float):
        await self._connect()

        data = json.dumps({'feed': feed, 'pair': pair, 'timestamp': timestamp,
                           'bid': str(bid), 'ask': str(ask)}).encode('utf8')
        topic =  f"{self.key}-{feed}-{pair}" if self.key else f"ticker-{feed}-{pair}"
        await self.producer.send_and_wait(topic, data)

'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import asyncio

from aiokafka import AIOKafkaProducer
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback


class KafkaCallback:
    def __init__(self, bootstrap='127.0.0.1', port=9092, key=None, numeric_type=float, **kwargs):
        self.bootstrap = bootstrap
        self.port = port
        self.producer = None
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type

    async def __connect(self):
        if not self.producer:
            loop = asyncio.get_event_loop()
            self.producer = AIOKafkaProducer(acks=0,
                                             loop=loop,
                                             bootstrap_servers=f'{self.bootstrap}:{self.port}',
                                             client_id='cryptofeed')
            await self.producer.start()

    async def write(self, data: dict):
        await self.__connect()
        topic = f"{self.key}-{data['exchange']}-{data['symbol']}"
        await self.producer.send_and_wait(topic, json.dumps(data).encode('utf-8'))


class TradeKafka(KafkaCallback, BackendCallback):
    default_key = 'trades'


class FundingKafka(KafkaCallback, BackendCallback):
    default_key = 'funding'


class BookKafka(KafkaCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, snapshot_interval=1000, **kwargs):
        self.snapshots_only = snapshots_only
        self.snapshot_interval = snapshot_interval
        self.snapshot_count = defaultdict(int)
        super().__init__(*args, **kwargs)


class TickerKafka(KafkaCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestKafka(KafkaCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsKafka(KafkaCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesKafka(KafkaCallback, BackendCallback):
    default_key = 'candles'

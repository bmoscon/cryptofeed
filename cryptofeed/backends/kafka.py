'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import asyncio
from typing import Optional

from aiokafka import AIOKafkaProducer
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback


class KafkaCallback:
    def __init__(self, bootstrap='127.0.0.1', port=9092, key=None, numeric_type=float, none_to=None, acks=0, client_id='cryptofeed', **kwargs):
        """
        bootstrap: str, list
            if a list, should be a list of strings in the format: ip/host:port, i.e.
                192.1.1.1:9092
                192.1.1.2:9092
                etc
            if a string, should be ip/port only
        """
        self.bootstrap = bootstrap
        self.port = port
        self.producer = None
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.acks = acks
        self.client_id = client_id

    async def __connect(self):
        if not self.producer:
            loop = asyncio.get_event_loop()
            self.producer = AIOKafkaProducer(acks=self.acks,
                                             loop=loop,
                                             bootstrap_servers=f'{self.bootstrap}:{self.port}' if isinstance(self.bootstrap, str) else self.bootstrap,
                                             client_id=self.client_id)
            await self.producer.start()

    def topic(self, data: dict) -> str:
        return f"{self.key}-{data['exchange']}-{data['symbol']}"

    def partition_key(self, data: dict) -> Optional[bytes]:
        return None

    def partition(self, data: dict) -> Optional[int]:
        return None

    async def write(self, data: dict):
        await self.__connect()
        await self.producer.send_and_wait(self.topic(data), json.dumps(data).encode('utf-8'), self.partition_key(data), self.partition(data))


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


class OrderInfoKafka(KafkaCallback, BackendCallback):
    default_key = 'order_info'


class TransactionsKafka(KafkaCallback, BackendCallback):
    default_key = 'transactions'


class BalancesKafka(KafkaCallback, BackendCallback):
    default_key = 'balances'


class FillsKafka(KafkaCallback, BackendCallback):
    default_key = 'fills'

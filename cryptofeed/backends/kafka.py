'''
Copyright (C) 2017-2022 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import asyncio
import logging
from typing import Optional, DefaultDict, List, Callable, ByteString

from aiokafka import AIOKafkaProducer
from aiokafka.errors import RequestTimedOutError
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue

LOG = logging.getLogger('feedhandler')


class KafkaCallback(BackendQueue):
    def __init__(self, producer_config: Optional[DefaultDict[str, str | List | int | Callable]] = None, key=None, numeric_type=float, none_to=None, **kwargs):
        """
        producer_config: dict
            A dictionary of configuration settings for AIOKafkaProducer.
            A full list of configuration parameters can be found at
            https://aiokafka.readthedocs.io/en/stable/api.html#aiokafka.AIOKafkaProducer  
            
            A 'value_serializer' option allows use of other schemas such as Avro, Protobuf etc. 
            The default serialization is JSON Bytes
            
            Example:
            
                {'bootstrap_servers': '127.0.0.1:9092',
                'client_id': 'cryptofeed',
                'acks': 1,
                'value_serializer': your_serialization_function}
                
            (the event loop is provided by Cryptofeed)
        """
        self.producer_config = producer_config or {
            'bootstrap_servers': '127.0.0.1:9092',
            'client_id': 'cryptofeed',
            'acks': 0
        }
        self.producer = None
        self.key: str = key or self.default_key
        self.numeric_type = numeric_type
        self.none_to = none_to
        self.running = True
    
    def _default_serializer(self, to_bytes: dict | str) -> ByteString:
        if isinstance(to_bytes, dict):
            return json.dumpb(to_bytes)
        elif isinstance(to_bytes, str):
            return to_bytes.encode()
        else:
            raise TypeError(f'{type(to_bytes)} is not a valid Serialization type')

    async def __connect(self):
        if not self.producer:
            loop = asyncio.get_event_loop()
            self.producer = AIOKafkaProducer(**self.producer_config, loop=loop)
            await self.producer.start()

    def topic(self, data: dict) -> str:
        return f"{self.key}-{data['exchange']}-{data['symbol']}"

    def partition_key(self, data: dict) -> Optional[bytes]:
        return None

    def partition(self, data: dict) -> Optional[int]:
        return None

    async def writer(self):
        await self._connect()
        LOG.info(f'{self.__class__.__name__}: {self.producer.client._client_id} connected to cluster containing {str(self.producer.client.cluster)[16:-1]}')
        while self.running:
            async with self.read_queue() as updates:
                for index in range(len(updates)):
                    topic = self.topic(updates[index])
                    value = updates[index] if self.producer_config.get('value_serializer') else self._default_serializer(updates[index])
                    key = self.key if self.producer_config.get('key_serializer') else self._default_serializer(self.key)
                    partition = self.partition(updates[index])
                    try:
                        await self.producer.send_and_wait(topic, value, key, partition)
                    except RequestTimedOutError:
                        LOG.error(f'{self.__class__.name}: No response received from server within {self.producer._request_timeout_ms} ms. Messages may not have been delivered')
                    except Exception as e:
                        LOG.info(f'{self.__class__.name}: Encountered an error:{chr(10)}{e}')
        LOG.info(f"{self.__class__.__name__}: sending last messages and closing connection '{self.producer.client._client_id}'")
        await self.producer.stop()


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

'''
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import asyncio
import logging
from typing import Optional, ByteString

from aiokafka import AIOKafkaProducer
from aiokafka.errors import RequestTimedOutError, KafkaConnectionError, NodeNotReadyError
from yapic import json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue

LOG = logging.getLogger('feedhandler')


class KafkaCallback(BackendQueue):
    def __init__(self, key=None, numeric_type=float, none_to=None, **kwargs):
        """
        You can pass configuration options to AIOKafkaProducer as keyword arguments.
        (either individual kwargs, an unpacked dictionary `**config_dict`, or both)
        A full list of configuration parameters can be found at
        https://aiokafka.readthedocs.io/en/stable/api.html#aiokafka.AIOKafkaProducer

        A 'value_serializer' option allows use of other schemas such as Avro, Protobuf etc.
        The default serialization is JSON Bytes

        Example:

            **{'bootstrap_servers': '127.0.0.1:9092',
            'client_id': 'cryptofeed',
            'acks': 1,
            'value_serializer': your_serialization_function}

        (Passing the event loop is already handled)
        """
        self.producer_config = kwargs
        self.producer = None
        self.key: str = key or self.default_key
        self.numeric_type = numeric_type
        self.none_to = none_to
        # Do not allow writer to send messages until connection confirmed
        self.running = False

    def _default_serializer(self, to_bytes: dict | str) -> ByteString:
        if isinstance(to_bytes, dict):
            return json.dumpb(to_bytes)
        elif isinstance(to_bytes, str):
            return to_bytes.encode()
        else:
            raise TypeError(f'{type(to_bytes)} is not a valid Serialization type')

    async def _connect(self):
        if not self.producer:
            loop = asyncio.get_event_loop()
            try:
                config_keys = ', '.join([k for k in self.producer_config.keys()])
                LOG.info(f'{self.__class__.__name__}: Configuring AIOKafka with the following parameters: {config_keys}')
                self.producer = AIOKafkaProducer(**self.producer_config, loop=loop)
            # Quit if invalid config option passed to AIOKafka
            except (TypeError, ValueError) as e:
                LOG.error(f'{self.__class__.__name__}: Invalid AIOKafka configuration: {e.args}{chr(10)}See https://aiokafka.readthedocs.io/en/stable/api.html#aiokafka.AIOKafkaProducer for list of configuration options')
                raise SystemExit
            else:
                while not self.running:
                    try:
                        await self.producer.start()
                    except KafkaConnectionError:
                        LOG.error(f'{self.__class__.__name__}: Unable to bootstrap from host(s)')
                        await asyncio.sleep(10)
                    else:
                        LOG.info(f'{self.__class__.__name__}: "{self.producer.client._client_id}" connected to cluster containing {len(self.producer.client.cluster.brokers())} broker(s)')
                        self.running = True

    def topic(self, data: dict) -> str:
        return f"{self.key}-{data['exchange']}-{data['symbol']}"

    def partition_key(self, data: dict) -> Optional[bytes]:
        return None

    def partition(self, data: dict) -> Optional[int]:
        return None

    async def writer(self):
        await self._connect()
        while self.running:
            async with self.read_queue() as updates:
                for index in range(len(updates)):
                    topic = self.topic(updates[index])
                    # Check for user-provided serializers, otherwise use default
                    value = updates[index] if self.producer_config.get('value_serializer') else self._default_serializer(updates[index])
                    key = self.key if self.producer_config.get('key_serializer') else self._default_serializer(self.key)
                    partition = self.partition(updates[index])
                    try:
                        send_future = await self.producer.send(topic, value, key, partition)
                        await send_future
                    except RequestTimedOutError:
                        LOG.error(f'{self.__class__.__name__}: No response received from server within {self.producer._request_timeout_ms} ms. Messages may not have been delivered')
                    except NodeNotReadyError:
                        LOG.error(f'{self.__class__.__name__}: Node not ready')
                    except Exception as e:
                        LOG.info(f'{self.__class__.__name__}: Encountered an error:{chr(10)}{e}')
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

'''
Copyright (C) 2017-2026 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from collections import defaultdict
import asyncio
import logging
import re
from contextlib import suppress
from typing import Optional

from aiokafka import AIOKafkaProducer
from aiokafka.errors import (InvalidTopicError, KafkaConnectionError, KafkaTimeoutError, MessageSizeTooLargeError, NodeNotReadyError, RecordListTooLargeError, RequestTimedOutError, UnknownTopicOrPartitionError)
from cryptofeed import _json as json

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback, BackendQueue, PermanentWriteError


LOG = logging.getLogger(__name__)


QUEUE_KWARGS = ('max_depth', 'overflow', 'batch_max', 'batch_interval', 'retry', 'flush_deadline')
PERMANENT_ERRORS = (MessageSizeTooLargeError, RecordListTooLargeError, InvalidTopicError)
TOPIC_MAX_LENGTH = 249
LEGAL_TOPIC = re.compile(r'^[A-Za-z0-9._-]+$')


def illegal_topic(name: str) -> Optional[str]:
    """Why `name` can never be a Kafka topic, or None if it can be one."""
    if not name or len(name) > TOPIC_MAX_LENGTH:
        return f'a topic name is 1-{TOPIC_MAX_LENGTH} characters, this one is {len(name)}'
    if name in ('.', '..'):
        return "'.' and '..' are not legal topic names"
    if not LEGAL_TOPIC.match(name):
        return 'a topic name may only contain [A-Za-z0-9._-]'
    return None


class KafkaCallback(BackendQueue):
    retryable_exceptions = (KafkaConnectionError, KafkaTimeoutError, NodeNotReadyError, RequestTimedOutError, UnknownTopicOrPartitionError)

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

        The queue options of BackendQueue (max_depth, overflow, batch_max, batch_interval,
        retry, flush_deadline) are accepted here too and go to the queue, not to the producer.
        """
        super().__init__(**{name: kwargs.pop(name) for name in QUEUE_KWARGS if name in kwargs})
        self.producer_config = kwargs
        self.producer = None
        self.key: str = key or self.default_key
        reason = illegal_topic(self.key)

        if reason is not None:
            raise ValueError(f'key {self.key!r} cannot be part of a Kafka topic name: {reason}')

        self.numeric_type = numeric_type
        self.none_to = none_to
        self._checked_topics = set()

    def _default_serializer(self, to_bytes: dict | str) -> bytes:
        if isinstance(to_bytes, dict):
            return json.dumpb(to_bytes)
        elif isinstance(to_bytes, str):
            return to_bytes.encode()
        else:
            raise TypeError(f'{type(to_bytes)} is not a valid Serialization type')

    async def connect(self):
        if self.producer is not None:
            return
        LOG.info('%s: Configuring AIOKafka with the following parameters: %s', self.__class__.__name__, ', '.join(self.producer_config.keys()))
        producer = AIOKafkaProducer(**self.producer_config)
        try:
            await producer.start()
        except BaseException:
            with suppress(Exception):
                await producer.stop()
            raise

        self.producer = producer
        LOG.info('%s: connected to a cluster containing %d broker(s)', self.__class__.__name__, len(producer.client.cluster.brokers()))

    def topic(self, data: dict) -> str:
        return f"{self.key}-{data['exchange']}-{data['symbol']}"

    def _topic(self, data: dict) -> str:
        name = self.topic(data)
        if name not in self._checked_topics:
            reason = illegal_topic(name)
            if reason is not None:
                raise PermanentWriteError(f'{name!r} is not a legal Kafka topic name: {reason}')
            self._checked_topics.add(name)
        return name

    def partition_key(self, data: dict) -> Optional[bytes]:
        return None

    def partition(self, data: dict) -> Optional[int]:
        return None

    async def write_batch(self, batch: list):
        results, interrupted = await self._send(batch)
        delivered = sum(not isinstance(result, BaseException) for result in results)
        permanent = None

        for result in results if interrupted is None else [*results, interrupted]:
            if not isinstance(result, BaseException):
                continue
            if not isinstance(result, PERMANENT_ERRORS + (PermanentWriteError,)):
                raise result
            if permanent is None:
                permanent = result

        if permanent is None:
            return None

        if not delivered:
            if isinstance(permanent, PermanentWriteError):
                raise permanent
            raise PermanentWriteError(str(permanent)) from permanent

        LOG.error('%s: kafka permanently rejected batch after %d of %d records already delivered (%s) - ', self.__class__.__name__, delivered, len(batch), permanent)
        return delivered, len(batch) - delivered

    async def _send(self, batch: list) -> tuple:
        value_serializer = self.producer_config.get('value_serializer')
        key = self.key if self.producer_config.get('key_serializer') else self._default_serializer(self.key)
        futures = []

        try:
            for update in batch:
                value = update if value_serializer else self._default_serializer(update)
                message_key = self.partition_key(update)
                futures.append(await self.producer.send(self._topic(update), value,
                                                        key if message_key is None else message_key,
                                                        self.partition(update)))
        except BaseException as e:
            results = await asyncio.gather(*futures, return_exceptions=True)
            if not isinstance(e, Exception):
                raise
            return results, e
        return await asyncio.gather(*futures, return_exceptions=True), None

    async def close(self):
        if self.producer is not None:
            producer, self.producer = self.producer, None
            LOG.info('%s: sending last messages and closing connection', self.__class__.__name__)
            await producer.stop()


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

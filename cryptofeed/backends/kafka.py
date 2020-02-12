'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio
import json

from aiokafka import AIOKafkaProducer

from cryptofeed.backends.backend import BackendBookCallback, BackendBookDeltaCallback, BackendFundingCallback, BackendTickerCallback, BackendTradeCallback, BackendOpenInterestCallback


class KafkaCallback:
    def __init__(self, bootstrap='127.0.0.1', port=9092, key=None, numeric_type=float, **kwargs):
        loop = asyncio.get_event_loop()
        self.producer = AIOKafkaProducer(acks=0,
                                         loop=loop,
                                         bootstrap_servers=f'{bootstrap}:{port}',
                                         client_id='cryptofeed')
        self.key = key if key else self.default_key
        self.numeric_type = numeric_type

    async def write(self, feed: str, pair: str, timestamp: float, data: dict):
        if self.producer._sender.sender_task is None:
            await self.producer.start()
        topic =  f"{self.key}-{feed}-{pair}"
        await self.producer.send_and_wait(topic, json.dumps(data).encode('utf-8'))


class TradeKafka(KafkaCallback, BackendTradeCallback):
   default_key = 'trades'


class FundingKafka(KafkaCallback, BackendFundingCallback):
    default_key = 'funding'


class BookKafka(KafkaCallback, BackendBookCallback):
    default_key = 'book'


class BookDeltaKafka(KafkaCallback, BackendBookDeltaCallback):
    default_key = 'book'


class TickerKafka(KafkaCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestKafka(KafkaCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'

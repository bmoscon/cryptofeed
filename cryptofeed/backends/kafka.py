'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import asyncio

from aiokafka import AIOKafkaProducer
from yapic import json

from cryptofeed.backends.backend import (BackendBookCallback, BackendBookDeltaCallback, BackendCandlesCallback, BackendFundingCallback,
                                         BackendOpenInterestCallback, BackendTickerCallback, BackendTradeCallback,
                                         BackendLiquidationsCallback, BackendMarketInfoCallback, BackendTransactionsCallback)


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

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        await self.__connect()
        topic = f"{self.key}-{feed}-{symbol}"
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


class LiquidationsKafka(KafkaCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class MarketInfoKafka(KafkaCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class TransactionsKafka(KafkaCallback, BackendTransactionsCallback):
    default_key = 'transactions'


class CandlesKafka(KafkaCallback, BackendCandlesCallback):
    default_key = 'candles'

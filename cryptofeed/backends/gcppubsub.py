'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import io
from typing import Optional
from typing import IO
from typing import Union
from typing import AnyStr

import aiohttp
import google.api_core.exceptions
from google.cloud import pubsub_v1
from yapic import json

# Use gcloud.aio.pubsub for asyncio
# https://github.com/talkiq/gcloud-aio
from gcloud.aio.pubsub import PublisherClient, PubsubMessage

from cryptofeed.backends.backend import (
    BackendBookCallback,
    BackendBookDeltaCallback,
    BackendFundingCallback,
    BackendLiquidationsCallback,
    BackendMarketInfoCallback,
    BackendOpenInterestCallback,
    BackendTickerCallback,
    BackendTradeCallback,
    BackendTransactionsCallback,
)


class GCPPubSubCallback:
    def __init__(self, topic: Optional[str] = None, key: Optional[str] = None,
                 service_file: Optional[Union[str, IO[AnyStr]]] = None,
                 client: Optional[PublisherClient] = None, session: Optional[aiohttp.ClientSession] = None,
                 ordering_key: Optional[Union[str, io.IOBase]] = None, numeric_type=float):
        '''
        Backend using Google Cloud Platform Pub/Sub. Use requires an account with Google Cloud Platform.
        Free tier allows 10GB messages per month.

        Both the environment variables GCP_PROJECT='<project_id>' and GOOGLE_APPLICATION_CREDENTIALS='/path/key.json'
        may be required.

        topic: str
            Topic name. Defaults to 'cryptofeed-{key}', for example 'cryptofeed-trades'
        key: str
            Setting key lets you override the symbol name.
            The defaults are related to the data
            being stored, i.e. trade, funding, etc
        service_file: str or file obj
            Loads credentials from a service account file.
            If not provided, credentials will be loaded from the environment variable
            'GOOGLE_APPLICATION_CREDENTIALS'. If inside a Google Cloud environment
            that has a default service account, such as Compute Engine, Google Kubernetes Engine,
            or App Engine the environment variable will already be set.
            https://cloud.google.com/bigquery/docs/authentication/service-account-file
            https://cloud.google.com/docs/authentication/production
        client: PublisherClient
            Allows gcloud.aio.pubsub.PublisherClient reuse
        session: ClientSession
            Allows aiohttp.ClientSession resuse
        ordering_key: str
            if messages have the same ordering key and you publish the messages
            to the same region, subscribers can receive the messages in order
            https://cloud.google.com/pubsub/docs/publisher#using_ordering_keys
        '''
        self.key = key or self.default_key
        self.ordering_key = ordering_key
        self.numeric_type = numeric_type
        self.topic = topic or f'cryptofeed-{self.key}'
        self.topic_path = self.get_topic()
        self.session = session or aiohttp.ClientSession()
        self.client = client or PublisherClient(service_file=service_file, session=self.session)

    def get_topic(self):
        publisher = pubsub_v1.PublisherClient()
        project_id = os.getenv('GCP_PROJECT')
        topic_path = PublisherClient.topic_path(project_id, self.topic)
        try:
            publisher.create_topic(topic_path)
        except google.api_core.exceptions.AlreadyExists:
            pass
        finally:
            return topic_path

    async def write(self, feed: str, symbol: str, timestamp: float, receipt_timestamp: float, data: dict):
        '''
        Publish message. For filtering, "feed" and "symbol" are added as attributes.
        https://cloud.google.com/pubsub/docs/filtering
        '''
        payload = json.dumps(data).encode()
        message = PubsubMessage(payload, feed=feed, symbol=symbol)
        await self.client.publish(self.topic_path, [message])


class TradeGCPPubSub(GCPPubSubCallback, BackendTradeCallback):
    default_key = 'trades'


class FundingGCPPubSub(GCPPubSubCallback, BackendFundingCallback):
    default_key = 'funding'


class BookGCPPubSub(GCPPubSubCallback, BackendBookCallback):
    default_key = 'book'


class BookDeltaGCPPubSub(GCPPubSubCallback, BackendBookDeltaCallback):
    default_key = 'book'


class TickerGCPPubSub(GCPPubSubCallback, BackendTickerCallback):
    default_key = 'ticker'


class OpenInterestGCPPubSub(GCPPubSubCallback, BackendOpenInterestCallback):
    default_key = 'open_interest'


class LiquidationsGCPPubSub(GCPPubSubCallback, BackendLiquidationsCallback):
    default_key = 'liquidations'


class MarketInfoGCPPubSub(GCPPubSubCallback, BackendMarketInfoCallback):
    default_key = 'market_info'


class TransactionsGCPPubSub(GCPPubSubCallback, BackendTransactionsCallback):
    default_key = 'transactions'

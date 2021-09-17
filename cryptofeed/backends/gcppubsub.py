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

from cryptofeed.backends.backend import BackendBookCallback, BackendCallback


class GCPPubSubCallback:
    def __init__(self, topic: Optional[str] = None, key: Optional[str] = None,
                 service_file: Optional[Union[str, IO[AnyStr]]] = None,
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
        self.service_file = service_file
        self.session = None
        self.client = None

    def get_topic(self):
        publisher = pubsub_v1.PublisherClient()
        project_id = os.getenv('GCP_PROJECT')
        topic_path = PublisherClient.topic_path(project_id, self.topic)
        try:
            publisher.create_topic(request={"name": topic_path})
        except google.api_core.exceptions.AlreadyExists:
            pass
        finally:
            return topic_path

    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session

    async def get_client(self):
        if not self.client:
            session = await self.get_session()
            self.client = PublisherClient(
                service_file=self.service_file, session=session
            )
        return self.client

    async def write(self, data: dict):
        '''
        Publish message. For filtering, "feed" and "symbol" are added as attributes.
        https://cloud.google.com/pubsub/docs/filtering
        '''
        client = await self.get_client()
        payload = json.dumps(data).encode()
        message = PubsubMessage(payload, feed=data['exchange'], symbol=data['symbol'])
        await client.publish(self.topic_path, [message])


class TradeGCPPubSub(GCPPubSubCallback, BackendCallback):
    default_key = 'trades'


class FundingGCPPubSub(GCPPubSubCallback, BackendCallback):
    default_key = 'funding'


class BookGCPPubSub(GCPPubSubCallback, BackendBookCallback):
    default_key = 'book'

    def __init__(self, *args, snapshots_only=False, **kwargs):
        self.snapshots_only = snapshots_only
        super().__init__(*args, **kwargs)


class TickerGCPPubSub(GCPPubSubCallback, BackendCallback):
    default_key = 'ticker'


class OpenInterestGCPPubSub(GCPPubSubCallback, BackendCallback):
    default_key = 'open_interest'


class LiquidationsGCPPubSub(GCPPubSubCallback, BackendCallback):
    default_key = 'liquidations'


class CandlesGCPPubSub(GCPPubSubCallback, BackendCallback):
    default_key = 'candles'

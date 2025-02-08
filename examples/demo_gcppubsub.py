'''
Copyright (C) 2018-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import asyncio

import aiohttp
from gcloud.aio.pubsub import subscribe, PublisherClient, SubscriberClient, SubscriberMessage
from yapic import json

from cryptofeed import FeedHandler
from cryptofeed.backends.gcppubsub import TradeGCPPubSub
from cryptofeed.defines import TRADES
from cryptofeed.exchanges import Coinbase


'''
Try it with the Pub/Sub emulator
--------------------------------
1. Install the emulator
https://cloud.google.com/pubsub/docs/emulator

2. Run the emulator
$ gcloud beta emulators pubsub start --host-port=0.0.0.0:8681

3. In another console, run the demo
$ export PUBSUB_EMULATOR_HOST='0.0.0.0:8681'; python examples/demo_gcppubsub.py


Try it with GCP Pub/Sub in the cloud
------------------------------------
1. Sign up for Google Cloud Platform (credit card is required)

2. If not using inside a Google Cloud environment that has a default service account,
such as Compute Engine, Google Kubernetes Engine https://cloud.google.com/docs/authentication/getting-started
$ export GOOGLE_APPLICATION_CREDENTIALS='/path/key.json'

3. Run the demo
$ export GCP_PROJECT='<project_id>'; python examples/demo_gcppubsub.py

'''


async def message_callback(message: SubscriberMessage) -> None:
    data = json.loads(message.data)
    print(data)


async def start_subscriber(topic):
    client = SubscriberClient()
    project_id = os.getenv("GCP_PROJECT")
    topic_path = PublisherClient.topic_path(project_id, topic)
    subscription_path = PublisherClient.subscription_path(project_id, topic)

    # Create subscription if it doesn't already exist
    try:
        await client.create_subscription(subscription_path, topic_path)
    except aiohttp.client_exceptions.ClientResponseError as e:
        if e.status == 409:  # Subscription exists
            pass
        else:
            raise TypeError("Please set the GCP_PROJECT environment variable") from e

    # For demo with Pub/Sub emulator, maybe ack_deadline_cache_timeout 300
    # On GCP, default seems fine.
    # For more options, check gcloud-aio docs:
    # https://github.com/talkiq/gcloud-aio/tree/master/pubsub
    await subscribe(subscription_path, message_callback, client, ack_deadline_cache_timeout=300)


def main():
    f = FeedHandler()

    trades = TradeGCPPubSub()
    cbs = {TRADES: trades}

    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks=cbs))
    f.run(start_loop=False)

    # Have the client run forever, pulling messages from subscription_path,
    # passing them to the specified callback function
    loop = asyncio.get_event_loop()
    loop.create_task(start_subscriber(trades.topic))
    loop.run_forever()


if __name__ == '__main__':
    main()

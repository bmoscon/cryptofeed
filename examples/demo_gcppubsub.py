'''
Copyright (C) 2018-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
import os
import asyncio
import google.api_core.exceptions

from gcloud.aio.pubsub import PublisherClient, SubscriberClient, SubscriberMessage
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
$ export PUBSUB_EMULATOR_HOST='0.0.0.0:8681' python examples/demo_gcppubsub.py


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
    try:
        data = json.loads(message.data)
    except Exception:
        message.nack()
    else:
        print(data)
        message.ack()


def start_subscriber(loop, topic):
    client = SubscriberClient()

    project_id = os.getenv('GCP_PROJECT')
    topic_path = PublisherClient.topic_path(project_id, topic)
    subscription_path = PublisherClient.subscription_path(project_id, topic)

    # Create subscription if it doesn't already exist
    try:
        client.create_subscription(subscription_path, topic_path)
    except google.api_core.exceptions.PermissionDenied as e:
        raise TypeError('Please set the GCP_PROJECT environment variable') from e

    # Subscribe to the subscription, receiving a Future that acts as a keepalive
    keep_alive = client.subscribe(subscription_path, message_callback)

    # Have the client run forever, pulling messages from this subscription,
    # passing them to the specified callback function, and wrapping it in an
    # asyncio task.
    client.run_forever(keep_alive)


def main():
    f = FeedHandler()

    trades = TradeGCPPubSub()

    cbs = {TRADES: trades}

    f.add_feed(Coinbase(channels=[TRADES], symbols=['BTC-USD'], callbacks=cbs))

    f.run(start_loop=False)

    loop = asyncio.get_event_loop()

    start_subscriber(loop, trades.topic)


if __name__ == '__main__':
    main()

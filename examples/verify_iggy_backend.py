"""Utility script to sanity-check the Iggy backend using the official SDK.

Launch an Iggy server (see docs/iggy_backend.md), run your Cryptofeed feed
handler configured with the Iggy backend, then execute this script to confirm
messages are landing in the expected stream/topic.

Usage (after installing apache-iggy):

    python examples/verify_iggy_backend.py \
        --connection-string iggy+tcp://iggy:iggy@127.0.0.1:8090 \
        --stream cryptofeed \
        --topic trades

The script polls for a bounded number of batches and prints each payload.
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Optional

from apache_iggy import IggyClient, PollingStrategy
from loguru import logger


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify Iggy backend output")
    parser.add_argument(
        "--connection-string",
        default="iggy+tcp://iggy:iggy@127.0.0.1:8090",
        help="Iggy connection string (scheme://user:password@host:port)",
    )
    parser.add_argument("--stream", default="cryptofeed", help="Stream name to inspect")
    parser.add_argument("--topic", default="trades", help="Topic name to inspect")
    parser.add_argument("--partition", type=int, default=1, help="Partition id to poll")
    parser.add_argument("--batches", type=int, default=5, help="Maximum batches to consume")
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="Number of messages to request per poll",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.5,
        help="Sleep interval between empty polls in seconds",
    )
    return parser.parse_args()


async def ensure_stream_topic(
    client: IggyClient,
    *,
    stream: str,
    topic: str,
    partition: int,
) -> None:
    """Replicate backend provisioning so the poller works even before data arrives."""

    existing_stream = await client.get_stream(stream)
    if existing_stream is None:
        logger.info("Stream %s missing, creating", stream)
        await client.create_stream(name=stream)

    existing_topic = await client.get_topic(stream, topic)
    if existing_topic is None:
        logger.info("Topic %s missing, creating", topic)
        await client.create_topic(stream=stream, name=topic, partitions_count=partition)


async def poll_messages(
    client: IggyClient,
    *,
    stream: str,
    topic: str,
    partition: int,
    batch_size: int,
    max_batches: int,
    interval: float,
) -> None:
    batches = 0
    from apache_iggy import ReceiveMessage  # local import for type hints

    while batches < max_batches:
        logger.debug(
            "Polling stream=%s topic=%s partition=%d", stream, topic, partition
        )
        messages: list[ReceiveMessage] = await client.poll_messages(
            stream=stream,
            topic=topic,
            partition_id=partition,
            polling_strategy=PollingStrategy.next(),
            count=batch_size,
            auto_commit=True,
        )

        if not messages:
            await asyncio.sleep(interval)
            continue

        logger.info("Received %d messages", len(messages))
        for message in messages:
            payload = message.payload().decode("utf-8", errors="replace")
            logger.info(
                "offset=%s timestamp=%s payload=%s",
                message.offset(),
                message.timestamp(),
                payload,
            )
        batches += 1


async def main() -> None:
    args = parse_args()
    client = IggyClient.from_connection_string(args.connection_string)
    await client.connect()
    logger.info("Connected to Iggy at %s", args.connection_string)
    await ensure_stream_topic(
        client,
        stream=args.stream,
        topic=args.topic,
        partition=args.partition,
    )
    await poll_messages(
        client,
        stream=args.stream,
        topic=args.topic,
        partition=args.partition,
        batch_size=args.batch_size,
        max_batches=args.batches,
        interval=args.interval,
    )


if __name__ == "__main__":
    asyncio.run(main())

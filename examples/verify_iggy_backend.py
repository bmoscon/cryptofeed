"""Verify Iggy backend output using the installed Apache SDK (>=0.5.0).

The current bindings expose asynchronous `IggyClient` helpers that expect
`host:port` endpoints (no `from_connection_string`). This script parses the
connection string documented in ``docs/iggy_backend.md``, connects/login, and
polls the configured stream/topic for a bounded number of batches.

Example usage::

    python examples/verify_iggy_backend.py \
        --connection-string iggy+tcp://iggy:iggy@127.0.0.1:8090 \
        --stream-id 1 --topic-id 1 --provision
"""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
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
    parser.add_argument("--stream-id", type=int, default=1, help="Numeric stream id")
    parser.add_argument("--stream-name", default="cryptofeed", help="Stream name when provisioning")
    parser.add_argument("--topic-id", type=int, default=1, help="Numeric topic id")
    parser.add_argument("--topic-name", default="trades", help="Topic name when provisioning")
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
        help="Sleep interval (seconds) between empty polls",
    )
    parser.add_argument(
        "--provision",
        action="store_true",
        help="Create stream/topic if they do not already exist",
    )
    return parser.parse_args()


@dataclass(slots=True)
class ParsedConnection:
    host: str
    port: int
    username: Optional[str]
    password: Optional[str]


def parse_connection_string(value: str) -> ParsedConnection:
    raw = value
    if raw.startswith("iggy+"):
        raw = raw[len("iggy+"):]
    if "//" in raw:
        raw = raw.split("//", 1)[1]
    creds, hostpart = raw.split("@", 1) if "@" in raw else (None, raw)
    host, port = hostpart.split(":", 1)
    username = password = None
    if creds:
        username, password = creds.split(":", 1)
    return ParsedConnection(host=host, port=int(port), username=username, password=password)


async def provision_resources(
    client: IggyClient,
    *,
    stream_id: int,
    stream_name: str,
    topic_id: int,
    topic_name: str,
) -> None:
    try:
        await client.create_stream(stream_id=stream_id, name=stream_name)
        logger.info("Created stream id=%s name=%s", stream_id, stream_name)
    except Exception:
        logger.debug("Stream %s already exists", stream_id)

    try:
        await client.create_topic(
            stream_id=stream_id,
            topic_id=topic_id,
            partitions_count=1,
            name=topic_name,
            compression_algorithm=None,
        )
        logger.info("Created topic id=%s name=%s", topic_id, topic_name)
    except Exception:
        logger.debug("Topic %s already exists", topic_id)


async def poll_messages(
    client: IggyClient,
    *,
    stream_id: int,
    topic_id: int,
    stream_name: str,
    topic_name: str,
    partition: int,
    batch_size: int,
    max_batches: int,
    interval: float,
) -> None:
    batches = 0
    while batches < max_batches:
        try:
            messages = await client.poll_messages(
                stream=stream_id,
                topic=topic_id,
                partition_id=partition,
                polling_strategy=PollingStrategy.Next(),
                count=batch_size,
                auto_commit=True,
            )
        except RuntimeError:
            messages = await client.poll_messages(
                stream=stream_name,
                topic=topic_name,
                partition_id=partition,
                polling_strategy=PollingStrategy.Next(),
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
    parsed = parse_connection_string(args.connection_string)
    client = IggyClient(f"{parsed.host}:{parsed.port}")
    await client.connect()
    logger.info("Connected to Iggy at %s:%s", parsed.host, parsed.port)
    if parsed.username and parsed.password:
        await client.login_user(parsed.username, parsed.password)
        logger.info("Authenticated as %s", parsed.username)

    if args.provision:
        await provision_resources(
            client,
            stream_id=args.stream_id,
            stream_name=args.stream_name,
            topic_id=args.topic_id,
            topic_name=args.topic_name,
        )

    await poll_messages(
        client,
        stream_id=args.stream_id,
        topic_id=args.topic_id,
        stream_name=args.stream_name,
        topic_name=args.topic_name,
        partition=args.partition,
        batch_size=args.batch_size,
        max_batches=args.batches,
        interval=args.interval,
    )


if __name__ == "__main__":
    asyncio.run(main())

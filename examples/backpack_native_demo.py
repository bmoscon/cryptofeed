"""Example script for running the native Backpack feed."""
from __future__ import annotations

import asyncio
import logging
import os

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, TRADES
from cryptofeed.exchanges.backpack import BackpackConfig, BackpackFeed


logging.basicConfig(level=logging.INFO)


async def handle_trade(trade, receipt_timestamp):
    logging.info("trade: %s @ %s", trade.amount, trade.price)


async def handle_l2(book, receipt_timestamp):
    levels = list(book.book.bids.items())[:1]
    logging.info("l2 snapshot seq=%s best_bid=%s", book.sequence_number, levels)


def main():
    os.environ.setdefault("CRYPTOFEED_BACKPACK_NATIVE", "true")

    config = BackpackConfig(
        enable_private_channels=False,
    )

    fh = FeedHandler()
    feed = BackpackFeed(
        config=config,
        symbols=["BTC-USDT"],
        channels=[TRADES, L2_BOOK],
        callbacks={
            TRADES: [handle_trade],
            L2_BOOK: [handle_l2],
        },
    )

    fh.add_feed(feed)
    fh.run(start_loop=True)


if __name__ == "__main__":
    main()

"""
Copyright (C) 2017-2025 Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
"""

from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, OPEN_INTEREST, TICKER, TRADES
from cryptofeed.exchanges import BinanceFutures, Coinbase
from cryptofeed.raw_data_collection import AsyncFileCallback


def main():
    f = FeedHandler(raw_data_collection=AsyncFileCallback("./"))
    f.add_feed(Coinbase(symbols=["BTC-USD"], channels=[L2_BOOK, TICKER, TRADES]))
    f.add_feed(BinanceFutures(symbols=["DOT-USDT", "BTC-USDT"], channels=[OPEN_INTEREST, L2_BOOK]))

    f.run()


if __name__ == "__main__":
    main()

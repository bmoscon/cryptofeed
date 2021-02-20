'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import L2_BOOK, TICKER, TRADES, OPEN_INTEREST, LIQUIDATIONS
from cryptofeed.exchanges import Coinbase, BinanceFutures
from cryptofeed.util.async_file import AsyncFileCallback
from cryptofeed.symbols import binance_futures_symbols


def main():
    f = FeedHandler(raw_message_capture=AsyncFileCallback('./'))
    f.add_feed(Coinbase(symbols=['BTC-USD'], channels=[L2_BOOK, TICKER, TRADES]))
    f.add_feed(BinanceFutures(symbols=binance_futures_symbols(), channels=[OPEN_INTEREST, LIQUIDATIONS]))

    f.run()


if __name__ == '__main__':
    main()

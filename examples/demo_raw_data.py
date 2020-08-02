'''
Copyright (C) 2017-2020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.defines import L3_BOOK, TICKER, TRADES
from cryptofeed.exchanges import Coinbase
from cryptofeed.util.async_file import AsyncFileCallback


def main():
    f = FeedHandler(raw_message_capture=AsyncFileCallback('./'), handler_enabled=False)
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L3_BOOK, TICKER, TRADES]))

    f.run()


if __name__ == '__main__':
    main()

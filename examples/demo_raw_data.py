'''
Copyright (C) 20172020  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.util.async_file import AsyncFileCallback
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase
from cryptofeed.defines import L2_BOOK


def main():
    f = FeedHandler(raw_message_capture=AsyncFileCallback('./'))
    f.add_feed(Coinbase(pairs=['BTC-USD'], channels=[L2_BOOK]))

    f.run()


if __name__ == '__main__':
    main()

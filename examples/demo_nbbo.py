'''
Copyright (C) 2017-2019  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase, Kraken, Gemini


def nbbo_update(pair, bid, bid_size, ask, ask_size, bid_feed, ask_feed):
    print(f'Pair: {pair} Bid Price: {bid:.2f} Bid Size: {bid_size:.6f} Bid Feed: {bid_feed} Ask Price: {ask:.2f} Ask Size: {ask_size:.6f} Ask Feed: {ask_feed}')


def main():
    f = FeedHandler()
    f.add_nbbo([Coinbase, Kraken, Gemini], ['BTC-USD'], nbbo_update)
    f.run()


if __name__ == '__main__':
    main()

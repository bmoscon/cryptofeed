'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.feedhandler import FeedHandler
from cryptofeed import GDAX, Bitfinex, HitBTC


def nbbo_ticker(pair, bid, ask, bid_feed, ask_feed):
    print('Pair: {} Bid: {:.2f} Bid Feed: {} Ask: {:.2f} Ask Feed: {}'.format(pair, bid, bid_feed, ask, ask_feed))


def main():
    f = FeedHandler()
    f.add_nbbo([GDAX, HitBTC, Bitfinex], ['BTC-USD', 'ETH-USD'], nbbo_ticker)
    f.run()

if __name__ == '__main__':
    main()


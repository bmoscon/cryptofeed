'''
Copyright (C) 2017-2021  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed import FeedHandler
from cryptofeed.exchanges import Coinbase, Gemini, Kraken


def nbbo_update(symbol, bid, bid_size, ask, ask_size, bid_feed, ask_feed):
    print(f'Pair: {symbol} Best Bid Price: {bid:.2f} Best Bid Size: {bid_size:.6f} Best Bid Exchange: {bid_feed}\nBest Ask Price: {ask:.2f} Best Ask Size: {ask_size:.6f} Best Ask Feed: {ask_feed}\n')


def main():
    f = FeedHandler()
    f.add_nbbo([Coinbase, Kraken, Gemini], ['BTC-USD'], nbbo_update)
    f.run()


if __name__ == '__main__':
    main()

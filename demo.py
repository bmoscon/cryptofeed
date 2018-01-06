'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback
from cryptofeed import FeedHandler
from cryptofeed import GDAX, Bitfinex, Poloniex, Gemini, HitBTC


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
def ticker(feed, pair, bid, ask):
    print('Feed: {} Pair: {} Bid: {} Ask: {}'.format(feed, pair, bid, ask))


def trade(feed, pair, side, amount, price):
    print('Feed: {} Pair: {} side: {} Amount: {} Price: {}'.format(feed, pair, side, amount, price))


def book(b):
    print('book bid size is {} ask size is {}'.format(len(b['BTC-USD']['bid']), len(b['BTC-USD']['ask'])))


def main():
    f = FeedHandler()
    #f.add_feed(GDAX(pairs=['BTC-USD'], channels=['full'], callbacks={'book': BookCallback(book)}))
    f.add_feed(GDAX(pairs=['BTC-USD'], channels=['matches'], callbacks={'trades': TradeCallback(trade)}))
    f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=['trades'], callbacks={'trades': TradeCallback(trade)}))
    f.add_feed(Poloniex(channels=[1002], callbacks={'ticker': TickerCallback(ticker)}))
    f.add_feed(GDAX(pairs=['BTC-USD'], channels=['ticker'], callbacks={'ticker': TickerCallback(ticker)}))
    f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=['ticker'], callbacks={'ticker': TickerCallback(ticker)}))
    f.add_feed(Poloniex(channels=['USDT-BTC']))
    f.add_feed(Gemini(pairs=['BTC-USD'], callbacks={'trades': TradeCallback(trade)}))
    f.add_feed(HitBTC(channels=['ticker'], pairs=['BTC-USD'], callbacks={'ticker': TickerCallback(ticker)}))
    f.run()


if __name__ == '__main__':
    main()

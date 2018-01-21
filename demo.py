'''
Copyright (C) 2017-2018  Bryant Moscon - bmoscon@gmail.com

Please see the LICENSE file for the terms and conditions
associated with this software.
'''
from cryptofeed.callback import TickerCallback, TradeCallback, BookCallback
from cryptofeed import FeedHandler
from cryptofeed import GDAX, Bitfinex, Poloniex, Gemini, HitBTC, EXX, Bitstamp


# Examples of some handlers for different updates. These currently don't do much.
# Handlers should conform to the patterns/signatures in callback.py
# Handlers can be normal methods/functions or async. The feedhandler is paused
# while the callbacks are being handled (unless they in turn await other functions or I/O)
# so they should be as lightweight as possible
async def ticker(feed, pair, bid, ask):
    print('Feed: {} Pair: {} Bid: {} Ask: {}'.format(feed, pair, bid, ask))


async def trade(feed, pair, side, amount, price):
    print('Feed: {} Pair: {} side: {} Amount: {} Price: {}'.format(feed, pair, side, amount, price))


async def book(feed, book):
    for pair in book:
        print('feed {} book bid size is {} ask size is {}'.format(feed, len(book[pair]['bid']), len(book[pair]['ask'])))


def main():
    f = FeedHandler()
    # f.add_feed(GDAX(pairs=['BTC-USD'], channels=['full'], callbacks={'book': BookCallback(book)}))
    # f.add_feed(GDAX(pairs=['BTC-USD'], channels=['matches'], callbacks={'trades': TradeCallback(trade)}))
    # f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=['trades'], callbacks={'trades': TradeCallback(trade)}))
    # f.add_feed(Poloniex(channels=[1002], callbacks={'ticker': TickerCallback(ticker)}))
    # f.add_feed(GDAX(pairs=['BTC-USD'], channels=['ticker'], callbacks={'ticker': TickerCallback(ticker)}))
    # f.add_feed(Bitfinex(pairs=['BTC-USD'], channels=['ticker'], callbacks={'ticker': TickerCallback(ticker)}))
    #f.add_feed(Poloniex(channels=['USDT-BTC'], callbacks={'book': BookCallback(book), 'trades': TradeCallback(trade)}))
    # f.add_feed(Gemini(pairs=['BTC-USD'], callbacks={'trades': TradeCallback(trade)}))
    # f.add_feed(HitBTC(channels=['trades'], pairs=['BTC-USD'], callbacks={'trades': TradeCallback(trade)}))
    #f.add_feed(EXX())
    f.add_feed(Bitstamp())
    f.run()


if __name__ == '__main__':
    main()
